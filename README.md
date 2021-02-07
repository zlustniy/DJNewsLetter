DJNewsLetter
==========

Данный проект демонстрирует возможности пакета для отправки писем.

## Системные требования

* Python == 3.7
* Django == 2.2

### Настройка почтового сервера

### mail.ru:

* host = smtp.mail.ru
* post = 465
* email_username = <your_mail@mail.ru>
* email_password = <your_password>

### Отправить письмо:

#### /mail/api/send_emails/

    {
        "emails": [
            "maxxim-zak@bk.ru",
            "devnull4@mail.ru"
        ]
    }

