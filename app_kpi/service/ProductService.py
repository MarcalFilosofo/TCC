from ast import If
from re import X
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from math import sqrt

from infra.DBConnection import DBConnection


class ProductService(object):
    def __init__(self):
        self.conn = DBConnection.getConnection()
        self.cmc = 90
        
    def get_taxa_convercao(self, product_id):
        taxa_convercao = 0.003
        return taxa_convercao

    def get_estoque_abc(self):
        self.conn.execute("""
            SELECT 
                COUNT(*) qt, 
                COUNT(*) / (SELECT COUNT(*) FROM wp_wc_order_product_lookup) * 100 as percentil, 
                wp_posts.post_title 
            FROM `wp_wc_order_product_lookup`
            INNER JOIN wp_posts ON wp_wc_order_product_lookup.product_id = wp_posts.ID
            GROUP BY wp_posts.ID  
            ORDER BY qt DESC;
        """)

        produtos_acumulados_tmp = self.conn.fetchall()

        produtos_acumulados = []
        percentual_tmp = 0
        total_a = 0
        total_b = 0
        total_c = 0
        total_prod_a = 0
        total_prod_b = 0
        total_prod_c = 0
        
        for p in produtos_acumulados_tmp:
            percentual_tmp += p['percentil']
            p['acumulado'] = percentual_tmp

            if(percentual_tmp <= 80):
                total_prod_a += 1
                total_a += float(p['qt'])
                classe = "A"
            elif(percentual_tmp > 80 and percentual_tmp <= 95):
                total_prod_b += 1
                total_b += float(p['qt'])
                classe = "B"
            else:
                total_prod_c += 1
                total_c += float(p['qt'])
                classe = "C"

            p['classe'] = classe
            produtos_acumulados.append(p)

        produtos_acumulados= dict({
            "total_a": total_a,
            "total_b": total_b,
            "total_c": total_c,
            "total_prod_a": total_prod_a,
            "total_prod_b": total_prod_b,
            "total_prod_c": total_prod_c,
            "produtos": produtos_acumulados
        })
     
        return produtos_acumulados

    def get_qt_orders(self, product_id):
        self.conn.execute("""
            SELECT COUNT(*) qt FROM `wp_wc_order_product_lookup`
            WHERE product_id  = %s
        """, [product_id])

        pedidos = pd.DataFrame(self.conn.fetchall())

        sum_compras = np.sum(list(pedidos['qt']))

        return sum_compras

    def get_index_recompra(self, product_id):
        self.conn.execute("""
            SELECT COUNT(*) qt, customer_id, product_id FROM `wp_wc_order_product_lookup`
            WHERE product_id  = %s
            GROUP BY customer_id, product_id
        """, [product_id])

        pedidos = pd.DataFrame(self.conn.fetchall())

        try:
            sum_compras = np.sum(list(pedidos['qt']))

            filter = pedidos['qt'] > 1

            recompras = pedidos.where(filter)
            sum_recompras = np.sum(list(recompras['qt'].fillna(0)))

            if (sum_compras == 0):
                return 0

            num_recompra = round(sum_recompras / sum_compras * 100, 2)
            return num_recompra
        except KeyError:
            return 0

    def get_products_kpis(self, valorCampanha):
        if valorCampanha is None:
            valorCampanha = 0

        valorCampanha = float(valorCampanha)
        self.conn.execute("""
            SELECT 
                wp_posts.ID,
                wp_posts.post_title,
                Round(Avg(DISTINCT(wp_commentmeta.meta_value)), 1) AS nps,
                -- COUNT(DISTINCT(wp_wc_order_product_lookup.product_id)) as qt_orders,
                COUNT(DISTINCT(wp_commentmeta.meta_id)) as rating_count,
                Round(wp_wc_product_meta_lookup.max_price, 2) as current_price,
                wp_wc_product_meta_lookup.stock_quantity,
                CASE 
                    WHEN wp_wc_product_meta_lookup.stock_status = "instock" THEN 1
                    ELSE 0
                END as stock_status
            FROM   wp_posts
                LEFT JOIN wp_comments
                        ON wp_posts.id = wp_comments.comment_post_id
                LEFT JOIN wp_commentmeta
                        ON wp_comments.comment_id = wp_commentmeta.comment_id
                -- LEFT JOIN wp_wc_order_product_lookup
                --        ON wp_posts.ID = wp_wc_order_product_lookup.product_id
                LEFT JOIN wp_wc_product_meta_lookup
                        ON wp_posts.ID = wp_wc_product_meta_lookup.product_id
            WHERE 
            (wp_commentmeta.meta_key = 'rating' OR wp_commentmeta.meta_key is null)
            AND wp_posts.post_type = "product"
            GROUP BY wp_posts.ID  
        """)

        products_kpis_1 = pd.DataFrame(self.conn.fetchall())

        products_kpis_list = []

        for index, row in products_kpis_1.iterrows():
            index_recompra = self.get_index_recompra(row['ID'])
            qt_orders = self.get_qt_orders(row['ID'])

            new_row = dict({
                "id": row['ID'],
                "post_title": row['post_title'],
                "current_price": row['current_price'],
                "nps": row['nps'],
                "stock_quantity": row['stock_quantity'],
                "stock_status": row['stock_status'],
                "qt_orders": qt_orders,
                # "rating_count": row['rating_count'],
                "repurchase": index_recompra,
            })
            products_kpis_list.append(new_row)

        products_kpi = pd.DataFrame(products_kpis_list)
        
        products_kpi['nps'] = products_kpi['nps'].fillna(0)

        self.conn.execute("""
            SELECT 
                max(wp_wc_product_meta_lookup.stock_quantity) as max_stock
            FROM   wp_wc_product_meta_lookup
        """)

        maior_quantidade_estoque = self.conn.fetchall()[0]['max_stock'] 
        maior_quantidade_estoque = maior_quantidade_estoque if maior_quantidade_estoque != None else 100

        products_kpi['stock_quantity'] = products_kpi['stock_quantity'].fillna(maior_quantidade_estoque)

        scaler = StandardScaler()

        products_kpi_2 = products_kpi
        scaled_data = scaler.fit_transform(products_kpi_2.drop(['current_price', 'post_title', 'id', 'stock_quantity'], axis=1))

        scaled_orders = pd.DataFrame(scaled_data)

        ratings = []

        for sd in scaled_data:
            ratings.append(np.mean(sd))

        min = float(np.min(ratings))
        max = float(np.max(ratings))

        new_ratings = list(
            map(
                lambda x: self.get_rating(min, max, x)
                , ratings
            )
        )

        X = np.array(products_kpi.drop(['post_title', 'id', 'current_price', 'stock_quantity'], axis=1))
        sum_of_squares = self.calculate_wcss(pd.DataFrame(X))
        n = self.optimal_number_of_clusters(sum_of_squares)

        kmeans = KMeans(n_clusters=n, random_state=0).fit(X)

        classes = list(map(self.padronizar_classe, kmeans.labels_))
        products_kpi['K_classes'] = classes
        products_kpi['rating'] = new_ratings

        total_rating = np.sum(new_ratings)

        products_kpi = products_kpi.sort_values(by='rating', ascending=False)

        valor_investido = []
        visitas_estimadas = []
        fat_estimado = []

        for index, row in products_kpi.iterrows():
            
            taxa_convercao = self.get_taxa_convercao(row['id'])

            if(taxa_convercao == 0):
                taxa_convercao = 1

            if(row['stock_quantity'] > 5):
                visitas_ideais = (int(row['stock_quantity']) - 5) / taxa_convercao
            else:
                visitas_ideais = (int(row['stock_quantity'])) / taxa_convercao

            valor_produto = round(visitas_ideais / 1000 * self.cmc, 2)

            if(valor_produto <= valorCampanha):
                valorCampanha = valorCampanha - valor_produto
            elif(valorCampanha > 0 and valor_produto > valorCampanha):
                valor_produto = valorCampanha
                valorCampanha = 0
            else:
                valor_produto = 0

            nu_visitas_estimada = round(valor_produto * self.cmc, 0)

            vendas_extimadas = int(nu_visitas_estimada * taxa_convercao)

            if(vendas_extimadas > row['stock_quantity']):
                valor_faturumento_estimado = float(row['current_price']) * (row['stock_quantity'] - 5) / 3
            else:
                valor_faturumento_estimado = float(row['current_price']) * vendas_extimadas / 3

            visitas_estimadas.append(nu_visitas_estimada)
            #fat_estimado.append(valor_faturumento_estimado)
            fat_estimado.append(f"{valor_faturumento_estimado:_.2f}".replace('.', ',').replace('_', '.'))

            valor_investido.append(round(valor_produto, 2))

        products_kpi['valor_investido'] = valor_investido
        products_kpi['visitas_estimadas'] = visitas_estimadas
        products_kpi['fat_estimado'] = fat_estimado

        products_kpi = products_kpi[products_kpi.valor_investido > 0]
        return products_kpi.to_dict('records')

    def get_rating(self, min, max, rating):
        if(min < 0):
            new_min = 0
            new_max = max + (min * -1)
            rating = rating + (min * -1)

        if(min > 0):
            new_min = 0
            new_max = max - min
            rating = rating - min


        fator_scaler = 10 / new_max

        new_rating = fator_scaler * rating

        return round(new_rating, 2)


    def calculate_wcss(self, data):
        wcss = []
        for n in range(2, 21):
            kmeans = KMeans(n_clusters=n)
            kmeans.fit(X=data)
            wcss.append(kmeans.inertia_)

        return wcss

    def optimal_number_of_clusters(self, wcss):
        x1, y1 = 2, wcss[0]
        x2, y2 = 20, wcss[len(wcss)-1]

        distances = []
        for i in range(len(wcss)):
            x0 = i+2
            y0 = wcss[i]
            numerator = abs((y2-y1)*x0 - (x2-x1)*y0 + x2*y1 - y2*x1)
            denominator = sqrt((y2 - y1)**2 + (x2 - x1)**2)
            distances.append(numerator/denominator)
        
        return distances.index(max(distances)) + 2


    def padronizar_classe(self, k_class):
        if(k_class == 1):
            return "D"
        
        if(k_class == 0):
            return "B"

        if(k_class == 2):
            return "C"

        if(k_class == 4):
            return "A"
