from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.forms import StudentForm
from app.models import Student
from app.services import refresh_enrollment_statuses, has_valid_scholarship

bp = Blueprint("students", __name__, url_prefix="/alunos")


@bp.route("/")
@login_required
def list_students():
    refresh_enrollment_statuses()
    q = (request.args.get("q") or "").strip()
    query = Student.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Student.name.ilike(like),
                Student.document.ilike(like),
                Student.phone.ilike(like),
                Student.email.ilike(like),
            )
        )
    students = query.order_by(Student.name).all()
    return render_template("students/list.html", students=students, q=q)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def create():
    form = StudentForm()
    if form.validate_on_submit():
        student = Student()
        _fill_student(student, form)
        db.session.add(student)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um aluno com este CPF.", "danger")
            return render_template("students/form.html", form=form, title="Novo aluno")
        flash("Aluno cadastrado.", "success")
        return redirect(url_for("students.detail", student_id=student.id))
    return render_template("students/form.html", form=form, title="Novo aluno")


@bp.route("/<int:student_id>")
@login_required
def detail(student_id):
    refresh_enrollment_statuses()
    student = Student.query.get_or_404(student_id)
    return render_template("students/detail.html", student=student, scholarship_active=has_valid_scholarship(student))


@bp.route("/<int:student_id>/editar", methods=["GET", "POST"])
@login_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    form = StudentForm(obj=student)
    if form.validate_on_submit():
        _fill_student(student, form)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um aluno com este CPF.", "danger")
            return render_template(
                "students/form.html", form=form, title="Editar aluno", student=student
            )
        flash("Aluno atualizado.", "success")
        return redirect(url_for("students.detail", student_id=student.id))
    return render_template(
        "students/form.html", form=form, title="Editar aluno", student=student
    )


def _fill_student(student, form):
    student.name = form.name.data.strip()
    student.document = form.document.data.strip()
    student.phone = (form.phone.data or "").strip() or None
    student.email = (form.email.data or "").strip() or None
    student.birth_date = form.birth_date.data
    student.status = form.status.data
    student.is_instructor = bool(form.is_instructor.data)
