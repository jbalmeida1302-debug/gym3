from flask import Blueprint, render_template
from flask_login import login_required

from app.services import dashboard_stats

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    stats = dashboard_stats()
    return render_template("dashboard.html", **stats)
