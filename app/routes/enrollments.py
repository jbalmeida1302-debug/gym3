from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.forms import EnrollmentForm
from app.models import Enrollment, Plan, Student
from app.services import cancel_enrollment, create_enrollment, refresh_enrollment_statuses, renew_enrollment

bp = Blueprint("enrollments", __name__, url_prefix="/matriculas")


@bp.route("/")
@login_required
def list_enrollments():
    refresh_enrollment_statuses()
    status = request.args.get("status") or ""
    query = Enrollment.query
    if status:
        query = query.filter_by(status=status)
    enrollments = query.order_by(Enrollment.end_date.desc()).all()
    return render_template(
        "enrollments/list.html", enrollments=enrollments, status=status
    )


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def create():
    form = EnrollmentForm()
    student_id = request.args.get("aluno", type=int)
    _set_choices(form, student_id)
    if not form.is_submitted():
        form.start_date.data = date.today()
        if student_id:
            form.student_id.data = student_id
    if form.validate_on_submit():
        student = Student.query.get_or_404(form.student_id.data)
        plan = Plan.query.get_or_404(form.plan_id.data)
        active = Enrollment.query.filter_by(student_id=student.id, status="ativa").first()
        if active:
            flash("Este aluno já possui uma matrícula ativa. Renove ou cancele a atual.", "warning")
            return render_template("enrollments/form.html", form=form, title="Nova matrícula")
        enrollment = create_enrollment(student, plan, form.start_date.data)
        db.session.commit()
        flash("Matrícula criada.", "success")
        return redirect(url_for("enrollments.list_enrollments"))
    return render_template("enrollments/form.html", form=form, title="Nova matrícula")


@bp.route("/<int:enrollment_id>/renovar", methods=["POST"])
@login_required
def renew(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    if enrollment.status == "cancelada":
        flash("Não é possível renovar uma matrícula cancelada.", "danger")
        return redirect(url_for("enrollments.list_enrollments"))
    renew_enrollment(enrollment)
    db.session.commit()
    flash("Matrícula renovada.", "success")
    return redirect(url_for("students.detail", student_id=enrollment.student_id))


@bp.route("/<int:enrollment_id>/cancelar", methods=["POST"])
@login_required
def cancel(enrollment_id):
    enrollment = Enrollment.query.get_or_404(enrollment_id)
    cancel_enrollment(enrollment)
    db.session.commit()
    flash("Matrícula cancelada.", "success")
    return redirect(url_for("students.detail", student_id=enrollment.student_id))


def _set_choices(form, student_id=None):
    students = Student.query.order_by(Student.name).all()
    if student_id:
        students = Student.query.filter_by(id=student_id).all() or students
    form.student_id.choices = [(s.id, f"{s.name} — {s.document}") for s in students]
    plans = Plan.query.filter_by(active=True).order_by(Plan.name).all()
    form.plan_id.choices = [
        (p.id, f"{p.name} ({p.duration_days} dias) — R$ {p.price}") for p in plans
    ]
