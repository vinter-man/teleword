from aiogram import Router

from teleword.bot.handlers import adding, admin, api, common, editing, export, fallback, lessons, statistic

# Order matters: the fallback router must stay last.
ROUTERS: list[Router] = [
    admin.router,
    common.router,
    adding.router,
    lessons.router,
    statistic.router,
    export.router,
    editing.router,
    api.router,
    fallback.router,
]
