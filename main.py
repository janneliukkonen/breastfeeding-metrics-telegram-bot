#!/usr/bin/env python
# -*- coding: UTF-8 -*-
"""
Python program to run Telegram Bot.

Generates inline buttons according to user input.

Asks information regarding breastfeeding activity and saves it in
database.
"""
import datetime
import logging
import math
import os
from uuid import uuid4
from typing import List, Tuple

import pytz
import telegram
from emoji import emojize
from influxdb import InfluxDBClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (CallbackContext, CallbackQueryHandler,
                          CommandHandler, Filters, PicklePersistence, Updater)


# Bot token
if not (API_TOKEN:= os.environ["TG_API_TOKEN"]):
    API_TOKEN="manually inputted"

PORT = 5005
URL = "https://tg.janli.dynu.net"
PERSISTENCE_FILE = PicklePersistence(filename='imetysbotpersistence')
TIME_INTERVAL_IN_MINUTES = 5
HOW_MANY_TIMESTAMPS = 35
BOOBS = ["Vasen", "Oikea"]
OTHER_BOOBS = ["Äidinmaito", "Korvike"]
# Amounts, if OTHER_BOOBS
FEEDING_AMOUNTS = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
POSITIONS = ["Makuultaan", "Kainalo", "Kapalo"]
DURATIONS = [1, 10, 20, 30, 40, 50, 60]

INFLUXDB_HOST = "192.168.1.150"
INFLUXDB_PORT = 8086
INFLUXDB_USER = "imetys"
INFLUXDB_PASSWORD = "imetyspassu"
INFLUXDB_DBNAME = "imetysbotti"
INFLUX_TAG_FIELDS = ["Boob", "Feeling", "Position"]
INFLUXDB_CLIENT = InfluxDBClient(INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_USER,
                                 INFLUXDB_PASSWORD, INFLUXDB_DBNAME)
ALLOW_CHAT_IDS = [-389766324, -351790824]

# Moods are now generated in own function, check below.
MOODS = []

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def send_graphs(update: Update):
    """TODO function, would generate graph of the results.

    :update: Update: object
    :context: CallBackContext object

    """
    msg = "Sorry, you are not allowed to use this bot."
    update.message.reply_text(msg)
    LOGGER.info(dir(update.message))


def askfeeling(update: Update, context: CallbackContext):
    """Asks for the user's current feeling.

    Generates reply buttons for different moods.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    LOGGER.debug("Chat ID: {}".format(update.effective_chat.id))
    key = str(uuid4())
    context.chat_data[key] = {}
    context.chat_data[key]["fields"] = {}
    chat_name = update.effective_chat.title
    if chat_name is None:
        chat_name = update.effective_chat.username
    context.chat_data[key]["chat"] = chat_name
    LOGGER.debug(update.effective_chat.username)
    LOGGER.debug(dir(context))
    LOGGER.debug(dir(update))
    LOGGER.debug(dir(update.effective_chat))
    LOGGER.debug(update.effective_chat.title)
    keyboard = []
    for mood in generate_mood_options():
        keyboard.append([
            InlineKeyboardButton(str(mood),
                                 callback_data="main|" + mood + "|" + key)
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = "How are you feeling?"
    update.message.reply_text(msg,
                              reply_markup=reply_markup,
                              parse_mode=telegram.ParseMode.MARKDOWN)


def askfeeling_backmenu(update: Update, context: CallbackContext):
    """Handles "back to feelings menu" button actions.

    Generates feelings list again.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    _, _, key = query.data.split("|")
    context.chat_data[key] = {}
    context.chat_data[key]["fields"] = {}
    keyboard = []
    for mood in generate_mood_options():
        keyboard.append([
            InlineKeyboardButton(str(mood), callback_data="main|" + mood + "|" + key)
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = "How are you feeling?"
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def main_menu(update: Update, context: CallbackContext):
    """Generates "main" menu.

    Different articles are defined in BOOBS and OTHER_BOOBS.

    Asks for what article (left, right, or bottle boob) is in question.
    Offers possibility to go back to previous menu.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    LOGGER.debug("Query data in main_menu is: {}".format(query.data))
    unused, value, key = query.data.split("|")

    chat_data_fields = context.chat_data[key]["fields"]
    chat_data_fields["Feeling"] = value
    first_row = [
        InlineKeyboardButton(boob, callback_data=boob + "|" + key)
        for boob in BOOBS
    ]
    second_row = [
        InlineKeyboardButton("Pullo (" + other_boob + ")",
                             callback_data=other_boob + "|" + key)
        for other_boob in OTHER_BOOBS
    ]
    third_row = [
        InlineKeyboardButton("Back to feelings selection",
                             callback_data="askfeeling|" + value + "|" + key)
    ]
    keyboard = [first_row, second_row, third_row]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = build_breastfeed_message(context.chat_data[key])
    msg += "\nNow select boob"
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def fed_by_instrument_menu(update: Update, context: CallbackContext):
    """Generates menu of possible amounts of fluid (e.g. milk).

    Different amounts are defined in FEEDING_AMOUNTS.

    Asks for estimation how much milk had been drank.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    value, key = query.data.split("|")
    chat_data = context.chat_data[key]
    chat_data_fields = context.chat_data[key]["fields"]
    chat_data_fields["Boob"] = value

    msg = build_breastfeed_message(chat_data)
    msg += "\nHow much, estimation?"

    # Add Boob to message

    row = []
    keyboard = []
    for counter, feeding_amount in enumerate(FEEDING_AMOUNTS, start=1):
        btn = InlineKeyboardButton(str(feeding_amount) + " ml",
                                   callback_data=str(feeding_amount) + "|" +
                                   key)
        row.append(btn)
        LOGGER.debug("ROW LENGTH: {}".format(len(row)))
        if counter % 5 == 0 and counter != -1:
            keyboard.append(row)
            row = []
    keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton("Back to boob selection",
                             callback_data="main|" +
                             chat_data_fields["Feeling"] + "|" + key)
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def position_menu(update: Update, context: CallbackContext):
    """Generates menu of available positions.

    Positions are defined in POSITIONS.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    value, key = query.data.split("|")
    chat_data = context.chat_data[key]
    chat_data_fields = context.chat_data[key]["fields"]
    chat_data_fields["Boob"] = value

    msg = build_breastfeed_message(chat_data)
    msg += "\nNow select position"

    query.edit_message_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN)
    # Add Boob to message

    keyboard = [[
        InlineKeyboardButton(position, callback_data=position + "|" + key)
        for position in POSITIONS
    ],
                [
                    InlineKeyboardButton("Back to boob selection",
                                         callback_data="main|" +
                                         chat_data_fields["Feeling"] + "|" +
                                         key)
                ]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def time_menu(update: Update, context: CallbackContext):
    """Generates menu of different moments im time
    around current time.

    Menu is configured through variables TIME_INTERVAL_IN_MINUTES
    and HOW_MANY_TIMESTAMPS.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    value, key = query.data.split("|")
    chat_data = context.chat_data[key]
    if value not in POSITIONS:
        # Then it is AMOUNT
        chat_data["fields"]["Amount"] = value
        chat_data["fields"]["Position"] = "NA"
    else:
        chat_data["fields"]["Position"] = value
        chat_data["fields"]["Amount"] = "NA"
    timestrs, datetimes = generate_timestamps()
    chat_data["datetimes"] = datetimes

    keyboard = []
    row = []
    for counter, time in enumerate(timestrs, start=-1):
        if counter == -1:
            btn = InlineKeyboardButton("Now (" + time + ")",
                                       callback_data="time|" + str(counter) +
                                       "|" + key)
            keyboard.append([btn])
            continue
        if not counter % 6:
            keyboard.append(row)
            row = []
        btn = InlineKeyboardButton(time,
                                   callback_data="time|" + str(counter) + "|" +
                                   key)
        row.append(btn)
    keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = build_breastfeed_message(chat_data)
    msg += "\nWhen was the feeding started?"
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def askfeedinglength_menu(update: Update, context: CallbackContext):
    """Generates menu for different feeding durations.

    Menu is configured through variable DURATIONS.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    _, index_value, key = query.data.split("|")
    chat_data = context.chat_data[key]
    LOGGER.debug(chat_data)

    value = chat_data["datetimes"][int(index_value) + 1]
    chat_data["fields"]["Time"] = value
    unused, datetimes = generate_timestamps()
    chat_data["datetimes"] = datetimes

    keyboard = [[
        InlineKeyboardButton(s, callback_data="duration|" + str(s) + "|" + key)
        for s in DURATIONS
    ]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    send_to_influxdb(chat_data["fields"], chat_data["chat"])
    msg = build_breastfeed_message(chat_data)
    msg += "\nHow long did the feeding take?"
    query.edit_message_text(text=msg,
                            reply_markup=reply_markup,
                            parse_mode=telegram.ParseMode.MARKDOWN)


def submit_duration_menu(update: Update, context: CallbackContext):
    """Action to be completed when user finishes all the menus.

    Sends information to the database and responses back to user.

    TODO: Add some error checking for database connections, e.g. let
    user know if the saving failured.

    :update: Update: Telegram library object
    :context: CallbackContext': TODO

    """
    query = update.callback_query
    _, value, key = query.data.split("|")
    chat_data = context.chat_data[key]

    chat_data["fields"]["Duration"] = value

    send_to_influxdb(chat_data["fields"], chat_data["chat"])
    msg = build_breastfeed_message(chat_data)
    msg += "\nGreat. Entry saved. Add another? /breastfeed"
    query.edit_message_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN)


def generate_timestamps() -> tuple: 
    """Generate timestamps around specific time with specific intervals.

    :returns: (String, Datetime): tuple of datetimes in string and datetime.

    """
    a = datetime.datetime.today()
    this_hour = datetime.datetime(
        a.year, a.month, a.day, a.hour,
        math.floor(a.minute / TIME_INTERVAL_IN_MINUTES) *
        TIME_INTERVAL_IN_MINUTES) - datetime.timedelta(
            minutes=HOW_MANY_TIMESTAMPS * (TIME_INTERVAL_IN_MINUTES))
    date_list = [
        this_hour + datetime.timedelta(minutes=TIME_INTERVAL_IN_MINUTES * x)
        for x in range(0, HOW_MANY_TIMESTAMPS + 1)
    ]
    date_list.insert(0, date_list[-1])
    return [x.strftime('%H:%M') for x in date_list], date_list


def help(update: Update):
    """Provides help answer if user calls /help

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    update.message.reply_text("Use /breastfeed to test this bot.")


def error(update: Update, context: CallbackContext):
    """Log errors caused by Updates.

    :update: Update: Telegram library object
    :context: CallbackContext: Telegram library object

    """
    query = update.callback_query
    query.edit_message_text(text="Something went wrong with TG.")
    LOGGER.warning('Update "%s" caused error "%s"', update, context.error)


def build_breastfeed_message(chat_data: dict) -> str:
    """Builds the message as user progresses through different menus.

    :chat_data: dict: Specific user's chat_data object from Telegram.
    :returns: string.

    """
    fields = chat_data["fields"]
    if len(fields) < 1:
        return "Select boob to begin."
    #  regex = r"Boob: (?P<Boob>\w+)\nPosition: (?P<Position>\w+)\nTime: (?P<Time>.+)$"
    return build_msg(fields)


def build_msg(fields: dict) -> str:
    """ Builds message for different phases of questionnaire.

    Builds dynamically new message after each Telegram question menu.

    :fields: dict: different fields.
    :returns: str: the message to be shown to user.

    """
    msg = ""
    for name, value in fields.items():
        if isinstance(value, datetime.date):
            msg += "*" + name + "*:\t" + value.strftime(
                "%Y-%m-%d %H:%M") + "\n"
        elif "Amount" in name and "NA" not in value:
            msg += "*" + name + "*:\t" + value + " ml\n"
        elif "Duration" in name:
            msg += "*" + name + "*:\t" + value + " min\n"
        else:
            msg += "*" + name + "*:\t" + value + "\n"
    return msg


def generate_mood_options(dbnames: bool = False) -> List[str]:
    """Generates list of different moods. Includes emojis.

    Boolean to control should we generate database values or
    values that we show to user (ux).

    :dbnames: bool: checks should it gene
    :returns: List: list of different mood strings.

    """
    if dbnames:
        # Could be switched later to whatever.
        ok = "ok"
        neutral = "neutral"
        bad = "bad"
        return [ok, neutral, bad]
    ok = emojize(':heart: Mainiota', use_aliases=True)
    neutral = emojize(':relieved: Meh', use_aliases=True)
    bad = emojize(':cold_sweat:Ugh.', use_aliases=True)
    return [ok, neutral, bad]


def format_db_values(fields: dict):
    """Wrapper function format uniform data towards database.
    E.g. if we change the strings shown to user afterwards,
    or if database backend is switched and we want to store data differently.

    Modifies fields object.

    :fields: TODO

    """
    for key in fields:
        if "Feeling" in key:
            feel_idx = generate_mood_options().index(fields[key])
            db_feel = generate_mood_options(dbnames=True)[feel_idx]
            fields[key] = db_feel


def send_to_influxdb(fields: dict, measurement_name: str):
    """Prepares data to the database. Initializes database table.
    Writes data to database.

    :fields: dict: contains write to be written.
    :measurement_name: str: Under what name should the data be written.

    """
    INFLUXDB_CLIENT.create_database(INFLUXDB_DBNAME)

    # Need temporary dict to separate Influxdb tags and values
    fields_tmp = dict(fields)
    time = fields_tmp["Time"].astimezone(pytz.utc)
    tags = {}
    LOGGER.debug("Fields bf: {}".format(fields_tmp))
    format_db_values(fields_tmp)
    for tag in INFLUX_TAG_FIELDS:
        tags[tag] = fields_tmp[tag]
        del fields_tmp[tag]
    del fields_tmp["Time"]
    if "Duration" not in fields_tmp:
        fields_tmp["Duration"] = "NA"

    LOGGER.debug("Fields: {}.".format(fields_tmp))
    # Convert all values to float
    for key in fields_tmp:
        if "NA" in fields_tmp[key]:
            fields_tmp[key] = float(0)
        else:
            fields_tmp[key] = float(fields_tmp[key])
    LOGGER.info(fields_tmp)
    # Format values to db
    LOGGER.info("Fields before format: {}".format(fields_tmp))
    LOGGER.info("Fields after format: {}".format(fields_tmp))
    json_body = [{
        "measurement": measurement_name,
        "tags": tags,
        "time": time,
        "fields": fields_tmp
    }]
    INFLUXDB_CLIENT.write_points(json_body)


def main():
    """
    Create the Updater and pass it your bot's token.
     Make sure to set use_context=True to use the new context based callbacks
     Post version 12 this will no longer be necessary
    """
    updater = Updater(API_TOKEN, use_context=True, persistence=PERSISTENCE_FILE)

    #  updater.dispatcher.add_handler(
    #  MessageHandler(Filters.chat(-1234), askfeeling))
    updater.dispatcher.add_handler(
        CommandHandler(
            'breastfeed',
            askfeeling,
            Filters.chat(ALLOW_CHAT_IDS) | Filters.private,
            pass_chat_data=True,
        ))
    updater.dispatcher.add_handler(
        CommandHandler(
            'graphs',
            send_graphs,
            Filters.chat(ALLOW_CHAT_IDS) | Filters.private,
            pass_chat_data=True,
        ))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(askfeeling_backmenu,
                             pattern="askfeeling",
                             pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(main_menu, pattern="main", pass_chat_data=True))

    for other_boob in OTHER_BOOBS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(fed_by_instrument_menu,
                                 pattern=other_boob,
                                 pass_chat_data=True))
    for boob in BOOBS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(position_menu,
                                 pattern=boob,
                                 pass_chat_data=True))
    for position in POSITIONS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(time_menu,
                                 pattern=position,
                                 pass_chat_data=True))
    for feeding_amount in FEEDING_AMOUNTS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(time_menu,
                                 pattern=str(feeding_amount),
                                 pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(askfeedinglength_menu,
                             pattern="time",
                             pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(submit_duration_menu,
                             pattern="duration",
                             pass_chat_data=True))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_error_handler(error)

    # add handlers

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT

    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=API_TOKEN)
    updater.bot.set_webhook(URL + "/" + API_TOKEN)
    updater.idle()


if __name__ == '__main__':
    main()
