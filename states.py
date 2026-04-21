from aiogram.dispatcher.filters.state import State, StatesGroup


class ClientCreateOrder(StatesGroup):
    district = State()
    problem = State()
    phone = State()
    media = State()


class MasterRegistration(StatesGroup):
    name = State()
    category = State()
    district = State()
    description = State()
    experience = State()
    phone = State()
    photo = State()


class OfferCreate(StatesGroup):
    price = State()
    eta = State()
    comment = State()


class SupportWrite(StatesGroup):
    text = State()


class SupportReply(StatesGroup):
    text = State()


class ComplaintWrite(StatesGroup):
    text = State()


class ProfileEdit(StatesGroup):
    value = State()
    category = State()


class RatingFlow(StatesGroup):
    value = State()
    review = State()


class ChatFlow(StatesGroup):
    message = State()
