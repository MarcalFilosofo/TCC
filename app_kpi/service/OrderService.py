from infra.DBConnection import DBConnection
import pandas as pd
from datetime import datetime, date, timedelta
 
class OrderService(object):

    def __init__(self):
        self.conn = DBConnection.getConnection()

    def get_lista_nps(self):
        self.conn.execute("""
            SELECT wp_posts.post_title, AVG(wp_commentmeta.meta_value) as nps FROM wp_posts
            INNER JOIN wp_comments ON wp_posts.ID = wp_comments.comment_post_ID
            INNER JOIN wp_commentmeta ON wp_comments.comment_ID = wp_commentmeta.comment_id
            WHERE
            wp_commentmeta.meta_key = 'rating'
            GROUP BY wp_posts.post_title
            ORDER BY nps DESC
        """)

        nps = pd.DataFrame(self.conn.fetchall())
        return nps

    def get_nps(self):
        self.conn.execute("""
            SELECT AVG(wp_commentmeta.meta_value) as nps FROM wp_posts
            INNER JOIN wp_comments ON wp_posts.ID = wp_comments.comment_post_ID
            INNER JOIN wp_commentmeta ON wp_comments.comment_ID = wp_commentmeta.comment_id
            WHERE
            wp_commentmeta.meta_key = 'rating'
            ORDER BY nps DESC
        """)

        nps = pd.DataFrame(self.conn.fetchall())
        return round(nps['nps'][0], 1)

    def get_ticket_medio(self):
        self.conn.execute("""
            SELECT AVG(total_sales) as avg FROM wp_wc_order_stats
        """)

        ticket_medio = pd.DataFrame(self.conn.fetchall())
        return round(ticket_medio['avg'][0], 2)

    def get_media_itens_carrinho(self):
        self.conn.execute("""
            SELECT AVG(num_items_sold) as avg FROM wp_wc_order_stats
        """)

        media_itens_carrinho = pd.DataFrame(self.conn.fetchall())
        return media_itens_carrinho['avg']

    def get_mrr(self):
        primeiro_dia_mes = datetime.today().strftime('%Y-%m') + "-01"
        hoje = datetime.today()

        self.conn.execute("""
            SELECT AVG(total_sales) mean FROM wp_wc_order_stats WHERE date_created BETWEEN %s AND %s
        """, [primeiro_dia_mes, hoje.strftime('%Y-%m-%d')])

        mrr_i = pd.DataFrame(self.conn.fetchall())

        dias_subtracao = int(datetime.today().strftime('%d')) + 1
        td = timedelta(dias_subtracao * -1)

        ultimo_dia_mes_passado = hoje + td
        ultimo_dia_mes_passado = ultimo_dia_mes_passado.strftime('%Y-%m-%d')

        dias_mes_passado = int((hoje + td).strftime('%d')) * -1
        td_2 = timedelta(dias_mes_passado)

        primeiro_dia_mes_passado = hoje + td + td_2
        primeiro_dia_mes_passado = primeiro_dia_mes_passado.strftime('%Y-%m-%d')

        self.conn.execute("""
            SELECT AVG(total_sales) mean FROM wp_wc_order_stats WHERE date_created BETWEEN %s AND %s
        """, [primeiro_dia_mes_passado, ultimo_dia_mes_passado])

        mrr_ii = pd.DataFrame(self.conn.fetchall())

        mrr_i = mrr_i['mean'][0]
        mrr_ii = mrr_ii['mean'][0]

        return [mrr_i, mrr_ii]

    def get_mensal(self):
        primeiro_dia_mes = datetime.today().strftime('%Y-%m') + "-01"

        ano_atual = datetime.today().strftime('%Y')
        dois_anos_atras = str(int(ano_atual) - 2) + "-" + datetime.today().strftime('%m-%d')

        qt_novos_clientes_mes_anterior = self.conn.execute("""
            SELECT
                count(*) as qt
            FROM wp_users
            INNER JOIN wp_wc_customer_lookup ON wp_users.ID = wp_wc_customer_lookup.user_id
            WHERE user_registered >= %s
        """, [primeiro_dia_mes])

        qt_novos_clientes_mes_anterior = pd.DataFrame(self.conn.fetchall())

        qt_clientes_perdios = self.conn.execute("""
            SELECT
                count(*) as qt
            FROM wp_wc_customer_lookup
            WHERE wp_wc_customer_lookup.date_last_active < %s
        """, [dois_anos_atras])

        qt_clientes_perdios = pd.DataFrame(self.conn.fetchall())

        churn_mensal = qt_clientes_perdios['qt'][0] / qt_novos_clientes_mes_anterior['qt'][0] * 100
        return churn_mensal

    def get_churn_bruto(self):
        mrr_i, mrr_ii = self.get_mrr()

        if mrr_i == None:
            return 1 * 100

        if mrr_ii == None:
            return 0 * 100

        return mrr_i / mrr_ii * 100

    def get_delta_tickt_medio(self):
        mrr_i, mrr_ii = self.get_mrr()
        if mrr_i == None:
            mrr_i = 0

        if mrr_ii == None:
            mrr_ii = 0

        upsells = mrr_i - mrr_ii
        return upsells

    def get_churn_liquido(self):
        upsell = self.get_delta_tickt_medio()
        mrr_i, mrr_ii = self.get_mrr()

        if mrr_i == None:
            mrr_i = 0

        if mrr_ii == None:
            mrr_ii = 0

        churn_liquido = mrr_i - upsell / mrr_ii * 100
        return churn_liquido

    def get_receita_liquida(self):
        ano_atual = datetime.today().strftime('%Y')
        hoje = datetime.today().strftime('%Y-%m-%d')
        dois_anos_atras = str(int(ano_atual) - 2) + "-" + datetime.today().strftime('%m-%d')

        receita_liquida_sql = self.conn.execute("""
            SELECT SUM(net_total) as nt FROM `wp_wc_order_stats` WHERE date_created BETWEEN %s AND %s
        """, [dois_anos_atras, hoje])

        receita_liquida = pd.DataFrame(self.conn.fetchall())
        receita_liquida = receita_liquida['nt'][0]
        return round(receita_liquida, 2)

    def get_ltv(self):
        churn_mensal = self.get_mensal()
        receita_liquida = self.get_receita_liquida()

        media_tv_cliente = 1 / churn_mensal
        kepler_ltv = receita_liquida * media_tv_cliente

        return kepler_ltv

    # TODO: pegar a taxa de conversão
    def get_taxa_conversao(self):
        return 0.05

    # TODO: pegar o cac
    def get_cac(self):
        return 20

    # TODO: pegar a taxa de desconto
    def get_taxa_desconto(self):
        return 0.11

    def get_clv(self):
        ano_atual = datetime.today().strftime('%Y')
        hoje = datetime.today().strftime('%Y-%m-%d')
        dois_anos_atras = str(int(ano_atual) - 2) + "-" + datetime.today().strftime('%m-%d')

        taxa_conversao = self.get_taxa_conversao()

        receita_liquida = self.get_receita_liquida()

        cac = self.get_cac()

        taxa_desconto = self.get_taxa_desconto()

        clv = receita_liquida * taxa_conversao / (1 + taxa_desconto) - cac
        return clv