# coding: utf-8
import os
from flask import (
    Flask, request, current_app, send_from_directory, render_template
)
from service.OrderService import OrderService


app = Flask(__name__)

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
app.config['MEDIA_ROOT'] = os.path.join(PROJECT_ROOT, 'media_files')

def converter_em_dict(var, label):
    return dict({label: var})

orderService = OrderService()

@app.route("/ticket-medio", methods=["GET"])
def return_ticket_medio():

    ticket_medio = orderService.get_ticket_medio()
    return converter_em_dict(ticket_medio, "ticket_medio") 

@app.route("/get-mrr", methods=["GET"])
def return_mrr():
    mrr = orderService.get_mrr()
    return converter_em_dict(mrr, "mrr") 

@app.route("/churn-liquido", methods=["GET"])
def return_churn_liquido():
    churn = orderService.get_churn_liquido()
    return converter_em_dict(churn, "churn_liquido")

@app.route("/receita-liquida", methods=["GET"])
def return_receita_liquida():
    receita_liquida = orderService.get_receita_liquida()
    return converter_em_dict(receita_liquida, "receita_liquida") 

@app.route("/ltv", methods=["GET"])
def return_ltv():
    ltv = orderService.get_ltv()
    return converter_em_dict(ltv, "ltv") 

@app.route("/clv", methods=["GET"])
def return_clv():
    clv = orderService.get_clv()
    return converter_em_dict(clv, "clv") 

@app.route("/nps", methods=["GET"])
def return_nps():
    nps = orderService.get_nps()
    return converter_em_dict(nps, "nps")

@app.route("/cac", methods=["GET"])
def return_cac():
    nps = orderService.get_cac()
    return converter_em_dict(nps, "cac") 

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True)