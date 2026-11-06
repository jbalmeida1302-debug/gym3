from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from app import db
from app.forms import PlanForm
from app.models import Plan

bp = Blueprint("plans", __name__, url_prefix="/planos")


@bp.route("/")
@login_required
def list_plans():
    plans = Plan.query.order_by(Plan.name).all()
    return render_template("plans/list.html", plans=plans)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def create():
    form = PlanForm()
    if form.validate_on_submit():
        plan = Plan()
        _fill_plan(plan, form)
        db.session.add(plan)
        db.session.commit()
        flash("Plano cadastrado.", "success")
        return redirect(url_for("plans.list_plans"))
    return render_template("plans/form.html", form=form, title="Novo plano")


@bp.route("/<int:plan_id>/editar", methods=["GET", "POST"])
@login_required
def edit(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    form = PlanForm(obj=plan)
    if not form.is_submitted():
        form.active.data = "1" if plan.active else "0"
    if form.validate_on_submit():
        _fill_plan(plan, form)
        db.session.commit()
        flash("Plano atualizado.", "success")
        return redirect(url_for("plans.list_plans"))
    return render_template("plans/form.html", form=form, title="Editar plano", plan=plan)


def _fill_plan(plan, form):
    plan.name = form.name.data.strip()
    plan.duration_days = form.duration_days.data
    plan.price = Decimal(form.price.data)
    plan.active = form.active.data == "1"
    plan.billing_cycle = form.billing_cycle.data
    plan.grace_days = form.grace_days.data
