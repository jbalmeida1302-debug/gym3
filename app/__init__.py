import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from werkzeug.security import generate_password_hash

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    # Carrega o .env localizado na raiz do projeto, independentemente da pasta
    # a partir da qual o comando python run.py foi executado.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(project_root, ".env"))
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "academia.db")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "")
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Defina SECRET_KEY em uma variável de ambiente antes de iniciar o sistema.")
    app.config["CONTROLID_BASE_URL"] = os.getenv("CONTROLID_BASE_URL", "").strip().rstrip("/")
    app.config["CONTROLID_USERNAME"] = os.getenv("CONTROLID_USERNAME", "").strip()
    app.config["CONTROLID_PASSWORD"] = os.getenv("CONTROLID_PASSWORD", "")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path.replace("\\", "/")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["WTF_CSRF_TIME_LIMIT"] = None

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Faça login para continuar."
    login_manager.login_message_category = "warning"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.routes.auth import bp as auth_bp
    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.enrollments import bp as enrollments_bp
    from app.routes.payments import bp as payments_bp
    from app.routes.plans import bp as plans_bp
    from app.routes.students import bp as students_bp
    from app.routes.facial_access import bp as facial_access_bp
    from app.routes.scholarships import bp as scholarships_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(students_bp)
    app.register_blueprint(plans_bp)
    app.register_blueprint(enrollments_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(facial_access_bp)
    app.register_blueprint(scholarships_bp)

    with app.app_context():
        db.create_all()
        _migrate_student_facial_columns()
        _migrate_scholarship_tables()
        _ensure_admin()

    return app


def _ensure_admin():
    from app.models import User

    if User.query.filter_by(username="admin").first():
        return
    admin = User(
        username="admin",
        name="Recepção",
        password_hash=generate_password_hash("admin123"),
    )
    db.session.add(admin)
    db.session.commit()


def _migrate_student_facial_columns():
    """Migração leve para bancos SQLite existentes; db.create_all não altera tabelas."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    if "student" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("student")}
    with db.engine.begin() as connection:
        if "controlid_user_id" not in columns:
            connection.execute(text("ALTER TABLE student ADD COLUMN controlid_user_id INTEGER"))
        if "face_registered" not in columns:
            connection.execute(text("ALTER TABLE student ADD COLUMN face_registered BOOLEAN NOT NULL DEFAULT 0"))
        if "is_instructor" not in columns:
            connection.execute(text("ALTER TABLE student ADD COLUMN is_instructor BOOLEAN NOT NULL DEFAULT 0"))
    tables = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        if "plan" in tables:
            plan_columns = {c["name"] for c in inspector.get_columns("plan")}
            if "grace_days" not in plan_columns:
                connection.execute(text("ALTER TABLE plan ADD COLUMN grace_days INTEGER NOT NULL DEFAULT 3"))
            if "billing_cycle" not in plan_columns:
                connection.execute(text("ALTER TABLE plan ADD COLUMN billing_cycle VARCHAR(20) NOT NULL DEFAULT 'mensal'"))
        if "payment" in tables:
            payment_columns = {c["name"] for c in inspector.get_columns("payment")}
            if "due_date" not in payment_columns:
                connection.execute(text("ALTER TABLE payment ADD COLUMN due_date DATE"))


def _migrate_scholarship_tables():
    """Cria tabelas da Bolsa Professor sem apagar os dados existentes."""
    db.create_all()
