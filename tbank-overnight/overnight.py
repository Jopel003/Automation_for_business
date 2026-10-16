import http.client
import json
import os
import ssl

from dotenv import load_dotenv

# Загружает переменные из файла .env рядом со скриптом
load_dotenv()


def require(name: str) -> str:
    """Возвращает значение переменной окружения или понятную ошибку.

    Используется при загрузке конфигурации из файла .env: если переменная
    не задана, скрипт падает сразу с понятным сообщением, а не посреди работы.

    Args:
        name (str): Имя переменной окружения (например, 'TBANK_API_TOKEN').

    Returns:
        str: Значение переменной окружения.

    Raises:
        RuntimeError: Если переменная не задана в окружении/.env.
    """
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f'Переменная {name} не задана — добавьте её в файл .env')
    return value


tt = require('TBANK_API_TOKEN')
tg = require('TELEGRAM_BOT_TOKEN')
chat_id = require('TELEGRAM_CHAT_ID')
main_account = require('TBANK_ACCOUNT_NUMBER')
agreement_number = require('OVERNIGHT_AGREEMENT_NUMBER')
certfile = require('CERTFILE')
keyfile = require('KEYFILE')

def get_ballance(token=tt, account=main_account):
    """Возвращает баланс указанного банковского счёта из T-Bank.

    Делает GET-запрос к OpenAPI (`/openapi/api/v4/bank-accounts`), собирает
    по всем счетам словарь вида `{accountNumber: balance}` и возвращает баланс
    запрошенного счёта.

    Args:
        token (str): Токен OpenAPI T-Bank (по умолчанию — `TBANK_API_TOKEN`).
        account (str): Номер счёта, чей баланс нужен
            (по умолчанию — `TBANK_ACCOUNT_NUMBER`).

    Returns:
        int: Баланс счёта в копейках (значение поля `balance.balance`).

    Raises:
        KeyError: Если переданный `account` отсутствует в ответе API.
    """
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
    """Пополняет овернайт-счёт на указанную сумму.

    Делает POST-запрос к закрытому OpenAPI Т-Банка (`secured-openapi.tbank.ru`,
    эндпоинт `/api/v1/overnight/replenish`) с mTLS-аутентификацией
    (сертификат + приватный ключ).

    Args:
        amount (int | float): Сумма пополнения в рублях (целая часть, в копейках
            не переводится — API ожидает рубли).
        agreement_number (str): Номер договора на овернайт.
        certfile (str): Путь к файлу клиентского сертификата mTLS.
        keyfile (str): Путь к приватному ключу mTLS.

    Returns:
        int: HTTP-статус ответа API (200 — успех, иначе — ошибка).
    """

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
        tg (str): Токен бота от @BotFather (`TELEGRAM_BOT_TOKEN`).
        chat_id (str | int): ID чата для отправки сообщения (`TELEGRAM_CHAT_ID`).
        message_text (str): Текст сообщения для отправки. Поддерживается
            HTML-разметка (`parse_mode='HTML'`).

    Returns:
        None: Если сообщение отправлено успешно (успех не возвращается явно).
        False: Если при отправке произошла ошибка (исключение перехвачено).
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
