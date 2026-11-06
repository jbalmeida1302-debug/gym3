from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Student, ProfessorScholarship, ScholarshipEvent
from app.services import has_valid_scholarship, synchronize_scholarship_billing

bp = Blueprint("scholarships", __name__, url_prefix="/bolsas-professor")


@bp.route("/")
@login_required
def index():
    scholarships = ProfessorScholarship.query.order_by(ProfessorScholarship.created_at.desc()).all()
    students = Student.query.order_by(Student.name).all()
    return render_template("scholarships/index.html", scholarships=scholarships, students=students)


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def create():
    instructors = Student.query.filter_by(is_instructor=True).order_by(Student.name).all()
    students = Student.query.order_by(Student.name).all()
    if request.method == "POST":
        instructor_id = request.form.get("instructor_id", type=int)
        family_id = request.form.get("family_id", type=int) or None
        relationship_type = (request.form.get("relationship_type") or "").strip() or None
        try:
            start_date = date.fromisoformat(request.form.get("start_date") or date.today().isoformat())
            end_raw = (request.form.get("end_date") or "").strip()
            end_date = date.fromisoformat(end_raw) if end_raw else None
        except ValueError:
            flash("Informe datas válidas.", "danger")
            return render_template("scholarships/form.html", instructors=instructors, students=students, today=date.today())
        instructor = db.session.get(Student, instructor_id) if instructor_id else None
        family = db.session.get(Student, family_id) if family_id else None
        if not instructor or not instructor.is_instructor or instructor.status != "ativo":
            flash("Selecione um instrutor cadastrado e ativo.", "danger")
        elif family and family.status != "ativo":
            flash("O familiar selecionado precisa estar ativo.", "danger")
        elif family and family.id == instructor.id:
            flash("O familiar deve ser uma pessoa diferente do instrutor.", "danger")
        elif family and not relationship_type:
            flash("Informe o parentesco do familiar.", "danger")
        elif end_date and end_date < start_date:
            flash("A data final não pode ser anterior à inicial.", "danger")
        elif ProfessorScholarship.query.filter_by(instructor_id=instructor.id).first():
            flash("Este instrutor já possui uma Bolsa Professor cadastrada.", "warning")
        else:
            scholarship = ProfessorScholarship(
                instructor=instructor, family=family, relationship_type=relationship_type,
                start_date=start_date, end_date=end_date, status="ativa",
                notes=(request.form.get("notes") or "").strip() or None,
                created_by_id=current_user.id,
            )
            db.session.add(scholarship)
            try:
                db.session.flush()
                # Só aplicar a isenção quando a bolsa já estiver vigente hoje.
                if scholarship.is_valid:
                    synchronize_scholarship_billing(scholarship, exempt=True)
                db.session.add(ScholarshipEvent(scholarship=scholarship, action="criada",
                    details="Bolsa integral concedida ao instrutor" + (" e familiar" if family else ""), user_id=current_user.id))
                db.session.commit()
                flash("Bolsa Professor cadastrada com gratuidade integral.", "success")
                return redirect(url_for("scholarships.index"))
            except IntegrityError:
                db.session.rollback()
                flash("Este familiar já está vinculado a outra bolsa. Cada familiar só pode constar em uma bolsa.", "danger")
    return render_template("scholarships/form.html", instructors=instructors, students=students, today=date.today())


@bp.route("/<int:scholarship_id>/<action>", methods=["POST"])
@login_required
def change_status(scholarship_id, action):
    scholarship = ProfessorScholarship.query.get_or_404(scholarship_id)
    actions = {"suspender": ("suspensa", "suspensa"), "reativar": ("ativa", "reativada"), "encerrar": ("encerrada", "encerrada")}
    if action not in actions:
        flash("Ação inválida.", "danger")
        return redirect(url_for("scholarships.index"))
    new_status, event_name = actions[action]
    scholarship.status = new_status
    # Ao reativar, isenta pendências; ao suspender/encerrar, retoma a cobrança.
    synchronize_scholarship_billing(
        scholarship, exempt=(new_status == "ativa" and scholarship.is_valid)
    )
    db.session.add(ScholarshipEvent(scholarship=scholarship, action=event_name,
        details=f"Status alterado para {new_status}", user_id=current_user.id))
    db.session.commit()
    flash(f"Bolsa {event_name}.", "success")
    return redirect(url_for("scholarships.index"))
