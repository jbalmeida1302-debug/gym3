from datetime import date, datetime, time, timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.controlid import ControlIDClient, ControlIDError
from app.models import AccessLog, Enrollment, Student
from app.services import access_decision, refresh_enrollment_statuses

bp = Blueprint("facial_access", __name__, url_prefix="/acesso-facial")


@bp.route("/")
@login_required
def index():
    students = Student.query.order_by(Student.name).all()
    logs = AccessLog.query.order_by(AccessLog.created_at.desc()).limit(50).all()
    configured = bool(current_app.config.get("CONTROLID_BASE_URL") and
                      current_app.config.get("CONTROLID_USERNAME") and
                      current_app.config.get("CONTROLID_PASSWORD"))
    access_states = {student.id: access_decision(student) for student in students}
    return render_template("facial_access/index.html", students=students, logs=logs,
                           configured=configured, access_states=access_states)


@bp.route("/historico")
@login_required
def history():
    """Histórico diário dos eventos conhecidos pelo FITGESTAO."""
    day_text = (request.args.get("dia") or date.today().isoformat()).strip()
    student_query = (request.args.get("aluno") or "").strip()
    result_filter = (request.args.get("resultado") or "").strip()
    try:
        selected_day = date.fromisoformat(day_text)
    except ValueError:
        selected_day = date.today()
        day_text = selected_day.isoformat()
    query = AccessLog.query.filter(
        AccessLog.created_at >= datetime.combine(selected_day, time.min),
        AccessLog.created_at < datetime.combine(selected_day + timedelta(days=1), time.min),
    )
    if student_query:
        query = query.filter(AccessLog.student_name.ilike(f"%{student_query}%"))
    if result_filter in {"autorizado", "negado", "erro", "pendente"}:
        query = query.filter(AccessLog.result == result_filter)
    logs = query.order_by(AccessLog.created_at.desc()).all()
    authorized = [log for log in logs if log.result == "autorizado"]
    unique_students = len({log.student_id for log in authorized if log.student_id is not None})
    return render_template("facial_access/history.html", logs=logs, dia=day_text,
                           aluno=student_query, resultado=result_filter,
                           authorized_count=len(authorized), unique_students=unique_students)


@bp.route("/testar-conexao", methods=["POST"])
@login_required
def test_connection():
    try:
        ControlIDClient().test_connection()
        flash("Conexão com a Control iD estabelecida.", "success")
    except ControlIDError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("facial_access.index"))


@bp.route("/cadastrar/<int:student_id>", methods=["POST"])
@login_required
def enroll(student_id):
    student = Student.query.get_or_404(student_id)
    refresh_enrollment_statuses()
    allowed, reason = access_decision(student)
    if not allowed:
        db.session.add(AccessLog(student_id=student.id, student_name=student.name,
            result="negado", reason=reason, source="cadastro facial"))
        db.session.commit()
        flash(f"Cadastro facial bloqueado pela regra de acesso: {reason}.", "warning")
        return redirect(url_for("facial_access.index"))
    try:
        client = ControlIDClient()
        # IDs locais são usados como IDs do usuário no terminal. Confirmar se não colidem com usuários já existentes.
        client.ensure_user(student.id, student.name)
        result = client.enroll_face(student.id)
        if result.get("success") is False:
            raise ControlIDError("O terminal recusou o cadastro facial. Confira a posição/qualidade da imagem e os detalhes no equipamento.")
        student.controlid_user_id = student.id
        # A API pode responder antes de concluir o processo em alguns firmwares; marcar como pendente evita falso sucesso.
        student.face_registered = bool(result.get("success") is True)
        db.session.add(AccessLog(student_id=student.id, student_name=student.name,
            result="autorizado" if student.face_registered else "pendente",
            reason="Cadastro facial confirmado pela API" if student.face_registered else "Cadastro iniciado; confirme a conclusão no terminal",
            source="cadastro facial"))
        db.session.commit()
        if student.face_registered:
            flash("Cadastro facial confirmado pela Control iD.", "success")
        else:
            flash("Cadastro iniciado. Confirme no terminal se a captura foi concluída; o sistema não marcou o rosto como confirmado.", "warning")
    except ControlIDError as exc:
        db.session.add(AccessLog(student_id=student.id, student_name=student.name,
            result="erro", reason=str(exc)[:255], source="cadastro facial"))
        db.session.commit()
        flash(f"Não foi possível iniciar o cadastro facial: {exc}", "danger")
    return redirect(url_for("facial_access.index"))
