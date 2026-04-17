from aiogram.dispatcher.filters.state import State, StatesGroup


# ---------- CLIENT ----------

class ClientCreateOrder(StatesGroup):
    district = State()
    problem = State()
    media = State()


class ClientCancelOrder(StatesGroup):
    confirm = State()


# ---------- MASTER ----------

class MasterRegistration(StatesGroup):
    name = State()
    category = State()
    district = State()
    description = State()
    experience = State()
    phone = State()
    photo = State()


# ---------- OFFERS ----------

class OfferCreate(StatesGroup):
    price = State()
    eta = State()
    comment = State()


# ---------- PROFILE ----------

class ProfileEdit(StatesGroup):
    value = State()


# ---------- SUPPORT ----------

class SupportWrite(StatesGroup):
    text = State()


class SupportReply(StatesGroup):
    text = State()


# ---------- COMPLAINT ----------

class ComplaintWrite(StatesGroup):
    text = State()


# ---------- RATING ----------

class RatingFlow(StatesGroup):
    value = State()
    review = State()


# ---------- CHAT ----------

class ChatFlow(StatesGroup):
    message = State()
