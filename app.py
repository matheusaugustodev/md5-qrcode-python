from flask import Flask, request, jsonify
import requests
from requests_oauthlib import OAuth1
from io import BytesIO
import hashlib
import magic
import cv2
from pyzbar.pyzbar import decode
import numpy as np
import fitz

# 2882020 imagem com qrcode
# 2915410 pdf com qrcode

def buscar_conteudo_qrcode(buffer_documento):
    imagem = cv2.imdecode(np.frombuffer(buffer_documento.getvalue(), dtype=np.uint8), flags=cv2.IMREAD_COLOR)
    codigos_qr = decode(imagem)

    for codigo_qr in codigos_qr:
        qr_code_do_buffer = codigo_qr.data.decode('utf-8')

        if qr_code_do_buffer[0: 3] == 'RPA':
            conteudo = qr_code_do_buffer
            return conteudo
     
def extrair_imagens_pdf(buffer_pdf):
    imagens = []
    doc = fitz.open('pdf', buffer_pdf)
    
    for pagina_num in range(doc.page_count):
        pagina = doc[pagina_num]
        imagens_da_pagina = pagina.get_images(full=True)
        
        for img_index, img_info in enumerate(imagens_da_pagina):
            imagem, _ = pagina.get_pixmap(image_index=img_index, clip=img_info['clip'])
            imagens.append(imagem)
    
    return imagens

def buscar_extensao_arquivo(buffer):
    try:
        tipo_mime = magic.from_buffer(buffer.read(), mime=True)
        extensao = tipo_mime.split('/')[1]
        return extensao
    except Exception as error:
        print('Erro buscar_extensao_arquivo(): ', error)


app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({ 'mensagem': 'Hello world, RENAPSI' })

@app.route('/buscardocumento', methods=['POST'])
def buscar_documento():
    try:
        data = request.json

        if not data:
            raise Exception('Corpo da solicitação inválido, faltou alguma informação')

        servidor = data.get('servidor')
        num_documento = data.get('numDocumento')
        consumer_key = data.get('consumerKey')
        consumer_secret = data.get('consumerSecret')
        access_token = data.get('accessToken')
        access_token_secret = data.get('accessTokenSecret')

        if not servidor or not num_documento or not consumer_key or not consumer_secret or not access_token or not access_token_secret:
            raise Exception('Corpo da solicitação inválido, faltou alguma informação')

        api_url = f'https://{servidor}.rpa.org.br/webdesk/streamcontrol/?WDCompanyId=31909&WDNrDocto={num_documento}&WDNrVersao=1000'

        headeroauth = OAuth1(consumer_key, consumer_secret,
                            access_token, access_token_secret,
                            signature_type='auth_header')
        response = requests.get(api_url, auth=headeroauth, verify=False)

        if not response.ok:
            raise Exception(f'Erro ao buscar arquivo na API do Fluig: {response.status_code} - {response.text}')

        buffer_arquivo = BytesIO(response.content)

        if buffer_arquivo.getbuffer().nbytes == 0:
            raise Exception('arquivo corrompido')

    
        extensao_arquivo = buscar_extensao_arquivo(buffer_arquivo)

        if extensao_arquivo not in ['jpg', 'jpeg', 'png', 'pdf']:
            raise Exception('Formato de arquivo não aceito: ' + extensao_arquivo)

        hash_string = hashlib.md5(buffer_arquivo.getvalue()).hexdigest()
        conteudo_qr_code = ''

        if (extensao_arquivo == 'pdf'):
            pdf_documento = fitz.open('pdf', response.content)

            for pagina_numero in range(pdf_documento.page_count):
                pagina = pdf_documento[pagina_numero]
                imagens_na_pagina = pagina.get_images(full=True)

            for img_index, imagem in enumerate(imagens_na_pagina):
                imagem_index = imagem[0]

                imagem_dict = pagina.get_image_info(imagem_index)
                imagem_stream = pdf_documento.extract_image(imagem_index)["image"]

                buffer_imagem = BytesIO(imagem_stream)

                conteudo_qr_code = buscar_conteudo_qrcode(buffer_imagem)
                if (conteudo_qr_code): break

            pdf_documento.close()

        else:
            conteudo_qr_code = buscar_conteudo_qrcode(buffer_arquivo)
           

        if conteudo_qr_code:
            partes_info = conteudo_qr_code.split('.')
            lista_infos_qrcode = {
                'CHAPA': partes_info[1],
                'CPF': partes_info[2],
                'MES': partes_info[3],
                'ANO': partes_info[4],
            }

            return jsonify({'MD5': hash_string, **lista_infos_qrcode})
        else:
            return jsonify({'MD5': hash_string})

    except Exception as error:
        print({'ERROR': str(error)})
        return jsonify({'ERROR': str(error)}), 500


if __name__ == '__main__':
   app.run()