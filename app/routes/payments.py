from datetime import date, datetime, time, timedelta
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.forms import PaymentForm
from app.models import Enrollment, Payment, Student
from app.services import create_next_invoice, refresh_enrollment_statuses, has_valid_scholarship

bp = Blueprint("payments", __name__, url_prefix="/pagamentos")


@bp.route("/")
@login_required
def list_payments():
    refresh_enrollment_statuses()
    view = request.args.get("view") or "todos"
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    # Cobranças históricas pagas/isentas permanecem no extrato; pendências de bolsistas
    # não devem aparecer como valores a receber.
    pending = [p for p in payments if p.status == "pendente"
               and not has_valid_scholarship(p.enrollment.student)]
    enrollments = Enrollment.query.filter(Enrollment.status.in_(["ativa", "vencida"])).all()
    delinquent = [e for e in enrollments
                  if e.is_delinquent and not has_valid_scholarship(e.student)]
    return render_template(
        "payments/list.html",
        payments=payments,
        pending=pending,
        delinquent=delinquent,
        view=view,
    )


@bp.route("/historico")
@login_required
def history():
    """Consulta independente do histórico financeiro; sem ações de cobrança."""
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    start_text = (request.args.get("inicio") or "").strip()
    end_text = (request.args.get("fim") or "").strip()
    query = Payment.query.join(Enrollment).join(Student)
    if q:
        query = query.filter(Student.name.ilike(f"%{q}%"))
    if status in {"pago", "pendente", "cancelado", "isento"}:
        query = query.filter(Payment.status == status)
    if start_text:
        try:
            start_date = date.fromisoformat(start_text)
            query = query.filter(Payment.created_at >= datetime.combine(start_date, time.min))
        except ValueError:
            start_text = ""
    if end_text:
        try:
            end_date = date.fromisoformat(end_text)
            query = query.filter(Payment.created_at < datetime.combine(end_date + timedelta(days=1), time.min))
        except ValueError:
            end_text = ""
    payments = query.order_by(Payment.created_at.desc()).all()
    total_paid = sum((p.amount for p in payments if p.status == "pago"), Decimal("0.00"))
    return render_template("payments/history.html", payments=payments, q=q, status=status,
                           inicio=start_text, fim=end_text, total_paid=total_paid)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def create():
    form = PaymentForm()
    enrollment_id = request.args.get("matricula", type=int)
    _set_choices(form)
    if not form.is_submitted():
        form.paid_at.data = date.today()
        form.due_date.data = date.today()
        if enrollment_id:
            form.enrollment_id.data = enrollment_id
            enrollment = Enrollment.query.get(enrollment_id)
            if enrollment:
                form.amount.data = enrollment.plan.price
    if form.validate_on_submit():
        enrollment = Enrollment.query.get_or_404(form.enrollment_id.data)
        if has_valid_scholarship(enrollment.student):
            flash("Este aluno possui Bolsa Professor válida. Não é permitido gerar cobrança.", "warning")
            return redirect(url_for("payments.list_payments"))
        # Se já existe uma cobrança pendente para esta matrícula, baixa essa cobrança
        # em vez de criar uma segunda cobrança duplicada.
        payment = Payment.query.filter_by(
            enrollment_id=enrollment.id, status="pendente"
        ).order_by(Payment.due_date.asc(), Payment.id.asc()).first()
        if payment:
            payment.amount = Decimal(form.amount.data)
            payment.method = form.method.data
            payment.status = form.status.data
            payment.notes = (form.notes.data or "").strip() or payment.notes
            payment.paid_at = form.paid_at.data if form.status.data == "pago" else None
            payment.due_date = form.due_date.data or payment.due_date or date.today()
            payment.user_id = current_user.id
        else:
            payment = Payment(
                enrollment=enrollment,
                user_id=current_user.id,
                amount=Decimal(form.amount.data),
                method=form.method.data,
                status=form.status.data,
                notes=(form.notes.data or "").strip() or None,
                paid_at=form.paid_at.data if form.status.data == "pago" else None,
                due_date=form.due_date.data or date.today(),
            )
            db.session.add(payment)
        db.session.flush()
        if payment.status == "pago":
            create_next_invoice(payment)
        db.session.commit()
        flash("Pagamento registrado.", "success")
        return redirect(url_for("payments.list_payments"))
    return render_template("payments/form.html", form=form, title="Registrar pagamento")


@bp.route("/<int:payment_id>/pagar", methods=["POST"])
@login_required
def mark_paid(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if has_valid_scholarship(payment.enrollment.student):
        flash("Aluno com Bolsa Professor válida: cobrança não deve ser recebida.", "warning")
        return redirect(url_for("payments.list_payments"))
    payment.status = "pago"
    payment.paid_at = date.today()
    if not payment.due_date:
        payment.due_date = date.today()
    create_next_invoice(payment)
    db.session.commit()
    flash("Pagamento marcado como pago.", "success")
    return redirect(url_for("payments.list_payments", view="pendentes"))


def _set_choices(form):
    enrollments = Enrollment.query.order_by(Enrollment.id.desc()).all()
    form.enrollment_id.choices = [
        (
            e.id,
            f"#{e.id} — {e.student.name} / {e.plan.name} ({e.status})",
        )
        for e in enrollments
    ]
