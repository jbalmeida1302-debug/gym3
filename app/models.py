from datetime import date, timedelta

from flask_login import UserMixin

from app import db
from sqlalchemy import or_


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    payments = db.relationship("Payment", backref="registered_by", lazy=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    document = db.Column(db.String(20), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ativo")
    is_instructor = db.Column(db.Boolean, nullable=False, default=False)
    controlid_user_id = db.Column(db.Integer, unique=True, nullable=True)
    face_registered = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    enrollments = db.relationship(
        "Enrollment", backref="student", lazy=True, order_by="Enrollment.start_date.desc()"
    )


class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    grace_days = db.Column(db.Integer, nullable=False, default=3)
    billing_cycle = db.Column(db.String(20), nullable=False, default="mensal")
    enrollments = db.relationship("Enrollment", backref="plan", lazy=True)


class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plan.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ativa")
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    payments = db.relationship(
        "Payment", backref="enrollment", lazy=True, order_by="Payment.paid_at.desc()"
    )

    @property
    def has_paid(self):
        return any(p.status == "pago" for p in self.payments)

    @property
    def is_delinquent(self):
        """Inadimplente quando existe cobrança vencida; bolsistas válidos são isentos."""
        if self.status != "ativa" or self.end_date < date.today():
            return False

        # Consultar a bolsa diretamente evita depender de backrefs já carregados
        # na sessão e cobre tanto o instrutor quanto o familiar indicado.
        student = self.student
        if student and student.status == "ativo":
            scholarship = ProfessorScholarship.query.filter(
                ProfessorScholarship.status == "ativa",
                ProfessorScholarship.start_date <= date.today(),
                or_(ProfessorScholarship.end_date.is_(None),
                    ProfessorScholarship.end_date >= date.today()),
                or_(ProfessorScholarship.instructor_id == student.id,
                    ProfessorScholarship.family_id == student.id),
            ).first()
            if scholarship and scholarship.instructor.status == "ativo":
                return False

        grace = max(0, self.plan.grace_days or 0)
        pending = [p for p in self.payments if p.status == "pendente"]
        if not pending:
            # Se já houve pagamento, a matrícula não pode ser marcada como
            # inadimplente apenas porque não há cobrança pendente no momento.
            if any(p.status == "pago" for p in self.payments):
                return False
            # Compatibilidade com matrículas antigas sem histórico financeiro.
            due = self.start_date
            return date.today() > due + timedelta(days=grace)
        return any(
            date.today() > (p.due_date or self.start_date) + timedelta(days=grace)
            for p in pending
        )

    @property
    def access_allowed(self):
        return (
            self.student.status == "ativo"
            and self.status == "ativa"
            and self.start_date <= date.today() <= self.end_date
            and not self.is_delinquent
        )


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollment.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid_at = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    method = db.Column(db.String(20), nullable=False, default="pix")
    status = db.Column(db.String(20), nullable=False, default="pendente")
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())


class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True)
    student_name = db.Column(db.String(120), nullable=True)
    result = db.Column(db.String(20), nullable=False)  # autorizado, negado, erro
    reason = db.Column(db.String(255), nullable=False)
    source = db.Column(db.String(40), nullable=False, default="painel")
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    student = db.relationship("Student", backref=db.backref("access_logs", lazy=True))


class ProfessorScholarship(db.Model):
    """Bolsa integral do instrutor e de, no máximo, um familiar indicado."""
    id = db.Column(db.Integer, primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False, unique=True)
    family_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=True, unique=True)
    relationship_type = db.Column(db.String(60), nullable=True)
    start_date = db.Column(db.Date, nullable=False, default=date.today)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="ativa")
    notes = db.Column(db.String(255), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    instructor = db.relationship("Student", foreign_keys=[instructor_id], backref=db.backref("instructor_scholarship", uselist=False))
    family = db.relationship("Student", foreign_keys=[family_id], backref=db.backref("family_scholarship", uselist=False))
    created_by = db.relationship("User", foreign_keys=[created_by_id])

    @property
    def is_valid(self):
        today = date.today()
        return (self.status == "ativa" and self.instructor.status == "ativo"
                and self.start_date <= today and (self.end_date is None or self.end_date >= today))


class ScholarshipEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scholarship_id = db.Column(db.Integer, db.ForeignKey("professor_scholarship.id"), nullable=False)
    action = db.Column(db.String(30), nullable=False)
    details = db.Column(db.String(255), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    scholarship = db.relationship("ProfessorScholarship", backref=db.backref("events", lazy=True, order_by="ScholarshipEvent.created_at.desc()"))
    user = db.relationship("User")
