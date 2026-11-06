from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from app import db
from app.models import Enrollment, Payment, Student, ProfessorScholarship


def refresh_enrollment_statuses():
    today = date.today()
    rows = Enrollment.query.filter(Enrollment.status != "cancelada").all()
    changed = False
    for enrollment in rows:
        new_status = "vencida" if enrollment.end_date < today else "ativa"
        if enrollment.status != new_status:
            enrollment.status = new_status
            changed = True
    if changed:
        db.session.commit()


def create_enrollment(student, plan, start_date=None):
    start = start_date or date.today()
    enrollment = Enrollment(
        student=student,
        plan=plan,
        start_date=start,
        end_date=start + timedelta(days=plan.duration_days),
        status="ativa",
    )
    db.session.add(enrollment)
    db.session.flush()
    # Bolsistas têm gratuidade integral: não gerar cobrança.
    if not has_valid_scholarship(student):
        db.session.add(Payment(
            enrollment=enrollment,
            amount=plan.price,
            method="pix",
            status="pendente",
            due_date=start,
            notes="Cobrança inicial gerada automaticamente",
        ))
    student.status = "ativo"
    return enrollment


def next_billing_date(current_date, cycle):
    """Avança um ciclo sem depender de bibliotecas externas."""
    from calendar import monthrange
    months = {"mensal": 1, "trimestral": 3, "semestral": 6, "anual": 12}
    if cycle not in months:
        return None
    month_index = current_date.month - 1 + months[cycle]
    year = current_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(current_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def create_next_invoice(payment):
    """Após quitar uma cobrança, agenda a próxima mensalidade do plano."""
    enrollment = payment.enrollment
    if has_valid_scholarship(enrollment.student):
        return None
    cycle = enrollment.plan.billing_cycle
    next_due = next_billing_date(payment.due_date or payment.paid_at or date.today(), cycle)
    if not next_due or next_due > enrollment.end_date:
        return None
    exists = Payment.query.filter_by(enrollment_id=enrollment.id, due_date=next_due).first()
    if exists:
        return exists
    invoice = Payment(
        enrollment=enrollment,
        amount=enrollment.plan.price,
        method="pix",
        status="pendente",
        due_date=next_due,
        notes="Próxima cobrança gerada após quitação",
    )
    db.session.add(invoice)
    return invoice


def renew_enrollment(enrollment):
    today = date.today()
    start = enrollment.end_date if enrollment.end_date >= today else today
    if start < today:
        start = today
    plan = enrollment.plan
    enrollment.start_date = start
    enrollment.end_date = start + timedelta(days=plan.duration_days)
    enrollment.status = "ativa"
    enrollment.student.status = "ativo"
    # Nova cobrança para o ciclo renovado, exceto para bolsistas.
    if not has_valid_scholarship(enrollment.student):
        db.session.add(Payment(
            enrollment=enrollment,
            amount=plan.price,
            method="pix",
            status="pendente",
            due_date=start,
            notes="Cobrança gerada na renovação da matrícula",
        ))
    return enrollment


def cancel_enrollment(enrollment):
    enrollment.status = "cancelada"


def dashboard_stats():
    refresh_enrollment_statuses()
    today = date.today()
    start_month = today.replace(day=1)
    end_month = today.replace(day=monthrange(today.year, today.month)[1])

    active_students = Student.query.filter_by(status="ativo").count()
    expired = Enrollment.query.filter_by(status="vencida").count()
    # Não contar cobranças antigas de pessoas atualmente cobertas por bolsa.
    pending_rows = Payment.query.filter_by(status="pendente").all()
    pending_payments = sum(
        1 for payment in pending_rows
        if not has_valid_scholarship(payment.enrollment.student)
    )

    paid_this_month = Payment.query.filter(
        Payment.status == "pago",
        Payment.paid_at >= start_month,
        Payment.paid_at <= end_month,
    ).all()
    revenue = sum((p.amount for p in paid_this_month), Decimal("0.00"))

    delinquent = [
        e
        for e in Enrollment.query.filter(Enrollment.status.in_(["ativa", "vencida"])).all()
        if e.is_delinquent and not has_valid_scholarship(e.student)
    ]

    recent_enrollments = (
        Enrollment.query.order_by(Enrollment.created_at.desc()).limit(8).all()
    )

    return {
        "active_students": active_students,
        "expired": expired,
        "pending_payments": pending_payments,
        "revenue": revenue,
        "delinquent_count": len(delinquent),
        "recent_enrollments": recent_enrollments,
        "delinquent": delinquent[:8],
    }



def has_valid_scholarship(student):
    """True se o aluno for instrutor ou familiar coberto por bolsa válida hoje."""
    if not student or student.status != "ativo":
        return False

    today = date.today()
    scholarship = ProfessorScholarship.query.filter(
        ProfessorScholarship.status == "ativa",
        ProfessorScholarship.start_date <= today,
        ((ProfessorScholarship.end_date.is_(None)) |
         (ProfessorScholarship.end_date >= today)),
        ((ProfessorScholarship.instructor_id == student.id) |
         (ProfessorScholarship.family_id == student.id)),
    ).first()

    return bool(scholarship and scholarship.instructor.status == "ativo")


def synchronize_scholarship_billing(scholarship, exempt):
    """Isenta cobranças pendentes ou retoma a cobrança ao suspender/encerrar a bolsa."""
    beneficiaries = [scholarship.instructor]
    if scholarship.family:
        beneficiaries.append(scholarship.family)

    for beneficiary in beneficiaries:
        beneficiary_is_exempt = exempt and has_valid_scholarship(beneficiary)
        for enrollment in beneficiary.enrollments:
            if enrollment.status != "ativa":
                continue
            pending = Payment.query.filter_by(
                enrollment_id=enrollment.id, status="pendente"
            ).all()
            if beneficiary_is_exempt:
                for payment in pending:
                    payment.status = "isento"
                    payment.notes = ((payment.notes or "") +
                                     " | Isento por Bolsa Professor").strip(" |")[:255]
            elif not pending:
                db.session.add(Payment(
                    enrollment=enrollment,
                    amount=enrollment.plan.price,
                    method="pix",
                    status="pendente",
                    due_date=date.today(),
                    notes="Cobrança retomada após suspensão/encerramento da Bolsa Professor",
                ))


def access_decision(student):
    """Regra central: bolsa válida dispensa matrícula e mensalidade."""
    today = date.today()
    if student.status != "ativo":
        return False, "Aluno inativo"
    if has_valid_scholarship(student):
        return True, "Acesso liberado: Bolsa Professor integral válida"
    enrollments = Enrollment.query.filter_by(student_id=student.id).all()
    current = [e for e in enrollments if e.status == "ativa" and e.start_date <= today <= e.end_date]
    if not current:
        return False, "Sem matrícula vigente"
    if any(e.is_delinquent for e in current):
        return False, "Pagamento vencido além do prazo de tolerância"
    return True, "Acesso liberado: matrícula vigente e financeiro em dia"
