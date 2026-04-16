ROLE_PERMISSION_GROUPS = {
    "users": {
        "label": "Пользователи и доступ",
        "items": [
            ("users.view", "Просмотр пользователей"),
            ("users.block", "Блокировка/разблокировка пользователей"),
            ("roles.manage", "Создание и настройка ролей"),
            ("roles.assign", "Назначение ролей пользователям"),
        ],
    },
    "memberships": {
        "label": "Состав отряда",
        "items": [
            ("memberships.view", "Просмотр состава отряда"),
            ("memberships.manage", "Управление составом отряда"),
        ],
    },
    "availability": {
        "label": "Доступности",
        "items": [
            ("availability.submit_self", "Заполнение своей доступности"),
            ("availability.view_all", "Просмотр всех ответов"),
            ("availability.manage_forms", "Создание и управление формами доступности"),
        ],
    },
    "schedule": {
        "label": "График",
        "items": [
            ("schedule.view_self", "Просмотр своего графика"),
            ("schedule.view_all", "Просмотр графика отряда"),
            ("schedule.generate", "Формирование графика"),
            ("schedule.edit", "Редактирование графика"),
            ("schedule.publish", "Публикация графика"),
        ],
    },
    "change_requests": {
        "label": "Заявки на изменения",
        "items": [
            ("change_requests.create_self", "Создание своей заявки"),
            ("change_requests.review", "Рассмотрение заявок"),
        ],
    },
    "attendance": {
        "label": "Посещаемость и QR",
        "items": [
            ("attendance.view_self_qr", "Просмотр своего QR"),
            ("attendance.scan_qr", "Сканирование QR"),
            ("attendance.mark", "Фиксация присутствия"),
        ],
    },
    "notifications": {
        "label": "Уведомления",
        "items": [
            ("notifications.send", "Отправка уведомлений"),
        ],
    },
}

ALL_ROLE_PERMISSION_CODES = {
    code
    for group in ROLE_PERMISSION_GROUPS.values()
    for code, _ in group["items"]
}