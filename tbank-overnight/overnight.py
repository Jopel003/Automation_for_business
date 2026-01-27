import http.client
import json
import ssl


with open('tokens.json', 'r', encoding='utf-8') as file:
    loaded_data = json.load(file)

tt = loaded_data['tbank_api_token']
tg = loaded_data['telegram_bot_token']
chat_id = loaded_data['telegram_chat_id']
main_account = loaded_data['tbank_account_number']
agreement_number = loaded_data['overnight_agreement_number']
certfile = loaded_data['certfile']
keyfile = loaded_data['keyfile']

def get_ballance(token=tt, account=main_account):
    conn = http.client.HTTPSConnection("business.tbank.ru")
    payload = ''
    headers = {
      'Accept': 'application/json',
      'Authorization': f'Bearer {token}'
    }
    conn.request("GET", "/openapi/api/v4/bank-accounts", payload, headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")
    accounts_data = json.loads(data)
    counter = {}
    for i in accounts_data:
        counter[i['accountNumber']] = i['balance']['balance']
    
    return(counter[account])

def transfer_to_overnight(amount, agreement_number, 
                          certfile=certfile, 
                          keyfile = keyfile
                          ):

    context = ssl.create_default_context()
    context.load_cert_chain(certfile, keyfile)
    conn = http.client.HTTPSConnection("secured-openapi.tbank.ru", context=context)

    amount = str(amount)

    path = f"/api/v1/overnight/replenish?agreementNumber={agreement_number}&amount={amount}"

    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {tt}'  # Ваш токен
    }

    payload = ''

    # Отправляем POST-запрос
    conn.request("POST", path, payload, headers)

    # Получаем ответ
    res = conn.getresponse()
    data = res.read()

    return(res.status)


def send_telegram_message(tg, chat_id, message_text):
    """
    Отправляет сообщение в Telegram через бота.
    
    Args:
        bot_token (str): Токен вашего бота от @BotFather
        chat_id (str или int): ID чата для отправки сообщения
        message_text (str): Текст сообщения для отправки
    
    Returns:
        bool: True если сообщение отправлено успешно, False в случае ошибки
    """
    try:
        # Создаем соединение с сервером Telegram
        conn = http.client.HTTPSConnection("api.telegram.org")
        
        # Формируем данные для отправки
        url = f"/bot{tg}/sendMessage"
        params = {
            'chat_id': chat_id,
            'text': message_text,
            'parse_mode': 'HTML'  # Можно использовать HTML-разметку
        }
        
        # Отправляем POST-запрос
        conn.request("POST", url, 
                     body=json.dumps(params), 
                     headers={'Content-Type': 'application/json'})
        
        # Получаем ответ
        response = conn.getresponse()
        
        # Закрываем соединение
        conn.close()
    except Exception as e:
        return False


amount = get_ballance()
amount = amount//1000*1000
ok = f'Овернайт пополнен на {amount} руб.'
oops = 'С овернайтом что-то не так, проверь'

if amount >= 100000:
    result = transfer_to_overnight(amount, agreement_number)
    send_telegram_message(tg, chat_id, ok if result == 200 else oops)
