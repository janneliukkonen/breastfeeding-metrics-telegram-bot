#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import datetime
import logging
import os
import re
from uuid import uuid4
import math
from dateutil.relativedelta import relativedelta

import pytz
import telegram
from emoji import emojize
from influxdb import InfluxDBClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (CallbackQueryHandler, CommandHandler, Filters,
                          MessageHandler, PicklePersistence, Updater)
TOKEN = "851577171:AAHgHXRJaXRvVLUvQPb9mzi3n06y19d6JKU"
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

INFLUXDB_CLIENT = InfluxDBClient(INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_USER,
                                 INFLUXDB_PASSWORD, INFLUXDB_DBNAME)
INFLUX_TAG_FIELDS = ["Boob", "Feeling", "Position"]

ALLOW_CHAT_IDs = [-389766324, -351790824]

# Moods are now generated in own function, check below.
MOODS = []

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)


def send_graphs(update, context):
    msg = "Sorry, you are not allowed to use this bot."
    update.message.reply_text(msg)
    logger.info(dir(update.message))


def askfeeling(update, context):
    logger.debug("Chat ID: " + str(update.effective_chat.id))
    key = str(uuid4())
    context.chat_data[key] = {}
    context.chat_data[key]["fields"] = {}
    chat_name = update.effective_chat.title
    if chat_name is None:
        chat_name = update.effective_chat.username
    context.chat_data[key]["chat"] = chat_name
    logger.debug(update.effective_chat.username)
    logger.debug(dir(context))
    logger.debug(dir(update))
    logger.debug(dir(update.effective_chat))
    logger.debug(update.effective_chat.title)
    keyboard = []
    for s in generate_mood_options():
        keyboard.append([
            InlineKeyboardButton(
                str(s), callback_data="main|" + s + "|" + key)
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = "How are you feeling?"
    update.message.reply_text(
        msg, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)


def askfeeling_backmenu(update, context):
    query = update.callback_query
    _, value, key = query.data.split("|")
    context.chat_data[key] = {}
    context.chat_data[key]["fields"] = {}
    keyboard = []
    for s in generate_mood_options():
        keyboard.append([
            InlineKeyboardButton(
                str(s), callback_data="main|" + s + "|" + key)
        ])
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = "How are you feeling?"
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def main_menu(update, context):
    query = update.callback_query
    logger.debug("Query data in main_menu is: " + query.data)
    _, value, key = query.data.split("|")

    chat_data = context.chat_data[key]
    chat_data_fields = context.chat_data[key]["fields"]
    chat_data_fields["Feeling"] = value
    first_row = [
        InlineKeyboardButton(s, callback_data=s + "|" + key) for s in BOOBS
    ]
    second_row = [
        InlineKeyboardButton("Pullo (" + s + ")", callback_data=s + "|" + key)
        for s in OTHER_BOOBS
    ]
    third_row = [
        InlineKeyboardButton(
            "Back to feelings selection",
            callback_data="askfeeling|" + value + "|" + key)
    ]
    keyboard = [first_row, second_row, third_row]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = build_breastfeed_message(context.chat_data[key])
    msg += "\nNow select boob"
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def fed_by_instrument_menu(update, context):
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
    for counter, s in enumerate(FEEDING_AMOUNTS, start=1):
        btn = InlineKeyboardButton(
            str(s) + " ml", callback_data=str(s) + "|" + key)
        row.append(btn)
        logger.debug("ROW LENGTH:" + str(len(row)))
        if counter % 5 == 0 and counter != -1:
            keyboard.append(row)
            row = []
    keyboard.append(row)
    keyboard.append([
        InlineKeyboardButton(
            "Back to boob selection",
            callback_data="main|" + chat_data_fields["Feeling"] + "|" + key)
    ])

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def position_menu(update, context):
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
        InlineKeyboardButton(s, callback_data=s + "|" + key) for s in POSITIONS
    ],
                [
                    InlineKeyboardButton(
                        "Back to boob selection",
                        callback_data="main|" + chat_data_fields["Feeling"] +
                        "|" + key)
                ]]

    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def time_menu(update, context):
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
    for counter, s in enumerate(timestrs, start=-1):
        if counter == -1:
            btn = InlineKeyboardButton(
                "Now (" + s + ")",
                callback_data="time|" + str(counter) + "|" + key)
            keyboard.append([btn])
            continue
        if not counter % 6:
            keyboard.append(row)
            row = []
        btn = InlineKeyboardButton(
            s, callback_data="time|" + str(counter) + "|" + key)
        row.append(btn)
    keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = build_breastfeed_message(chat_data)
    msg += "\nWhen was the feeding started?"
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def askfeedinglength_menu(update, context):
    query = update.callback_query
    _, index_value, key = query.data.split("|")
    chat_data = context.chat_data[key]
    logger.debug(chat_data)

    value = chat_data["datetimes"][int(index_value) + 1]
    chat_data["fields"]["Time"] = value
    timestrs, datetimes = generate_timestamps()
    chat_data["datetimes"] = datetimes

    keyboard = [[
        InlineKeyboardButton(
            s, callback_data="duration|" + str(s) + "|" + key)
        for s in DURATIONS
    ]]
    row = []

    reply_markup = InlineKeyboardMarkup(keyboard)
    send_to_influxdb(chat_data["fields"], chat_data["chat"])
    msg = build_breastfeed_message(chat_data)
    msg += "\nHow long did the feeding take?"
    query.edit_message_text(
        text=msg,
        reply_markup=reply_markup,
        parse_mode=telegram.ParseMode.MARKDOWN)


def submit_duration_menu(update, context):
    query = update.callback_query
    _, value, key = query.data.split("|")
    chat_data = context.chat_data[key]

    chat_data["fields"]["Duration"] = value

    send_to_influxdb(chat_data["fields"], chat_data["chat"])
    msg = build_breastfeed_message(chat_data)
    msg += "\nGreat. Entry saved. Add another? /breastfeed"
    query.edit_message_text(text=msg, parse_mode=telegram.ParseMode.MARKDOWN)


def generate_timestamps():
    
    a = datetime.datetime.today()
    this_hour= datetime.datetime(a.year,a.month,a.day,a.hour,math.floor(a.minute/TIME_INTERVAL_IN_MINUTES)*TIME_INTERVAL_IN_MINUTES) - datetime.timedelta(minutes=HOW_MANY_TIMESTAMPS * (TIME_INTERVAL_IN_MINUTES))
    date_list = [
        this_hour + datetime.timedelta(minutes=TIME_INTERVAL_IN_MINUTES * x)
        for x in range(0, HOW_MANY_TIMESTAMPS+1)
    ]
    date_list.insert(0, date_list[-1])
    return [x.strftime('%H:%M') for x in date_list], date_list


def button(update, context):
    query = update.callback_query

    query.edit_message_text(text="Selected option: {}".format(query.data))


def help(update, context):
    update.message.reply_text("Use /breastfeed to test this bot.")


def error(update, context):
    """Log Errors caused by Updates."""
    query = update.callback_query
    query.edit_message_text(text="Something went wrong with TG.")
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def build_breastfeed_message(chat_data):
    fields = chat_data["fields"]
    if len(fields) < 1:
        return "Select boob to begin."
    #  regex = r"Boob: (?P<Boob>\w+)\nPosition: (?P<Position>\w+)\nTime: (?P<Time>.+)$"
    return build_msg(fields)


def build_regex(fields):
    regex = ""
    for name in fields:
        regex += name + ": (?P<" + name + ">\\w+)\n"
    return regex


def build_msg(fields):
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


def generate_mood_options(dbnames=False):
    """Generate mood names with emojis."""
    if dbnames:
        ok = "ok"
        neutral = "neutral"
        bad = "bad"
        return [ok, neutral, bad]
    ok = emojize(':heart: Mainiota', use_aliases=True)
    neutral = emojize(':relieved: Meh', use_aliases=True)
    bad = emojize(':cold_sweat:Ugh.', use_aliases=True)
    return [ok, neutral, bad]


def format_db_values(fields):
    """Formats values correctly to the database.
       E.g. Feeling value should not have emojis
    """
    for key in fields:
        if "Feeling" in key:
            feel_idx = generate_mood_options().index(fields[key])
            db_feel = generate_mood_options(dbnames=True)[feel_idx]
            fields[key] = db_feel


def send_to_influxdb(fields, measurement_name):
    INFLUXDB_CLIENT.create_database(INFLUXDB_DBNAME)

    # Need temporary dict to separate Influxdb tags and values
    fields_tmp = dict(fields)
    time = fields_tmp["Time"].astimezone(pytz.utc)
    tags = {}
    logger.debug("Fields bf: " + str(fields_tmp))
    format_db_values(fields_tmp)
    for s in INFLUX_TAG_FIELDS:
        tags[s] = fields_tmp[s]
        del fields_tmp[s]
    del fields_tmp["Time"]
    if "Duration" not in fields_tmp:
        fields_tmp["Duration"] = "NA"

    logger.debug("Fields: " + str(fields_tmp))
    # Convert all values to float
    for key in fields_tmp:
        if "NA" in fields_tmp[key]:
            fields_tmp[key] = float(0)
        else:
            fields_tmp[key] = float(fields_tmp[key])
    logger.info(fields_tmp)
    # Format values to db
    logger.info("Fields before format: " + str(fields_tmp))
    logger.info("Fields after format: " + str(fields_tmp))
    json_body = [{
        "measurement": measurement_name,
        "tags": tags,
        "time": time,
        "fields": fields_tmp
    }]
    INFLUXDB_CLIENT.write_points(json_body)


def main():
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary

    updater = Updater(TOKEN, use_context=True, persistence=PERSISTENCE_FILE)

    #  updater.dispatcher.add_handler(
    #  MessageHandler(Filters.chat(-1234), askfeeling))
    updater.dispatcher.add_handler(
        CommandHandler(
            'breastfeed',
            askfeeling,
            Filters.chat(ALLOW_CHAT_IDs) | Filters.private,
            pass_chat_data=True,
        ))
    updater.dispatcher.add_handler(
        CommandHandler(
            'graphs',
            send_graphs,
            Filters.chat(ALLOW_CHAT_IDs) | Filters.private,
            pass_chat_data=True,
        ))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(
            askfeeling_backmenu, pattern="askfeeling", pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(main_menu, pattern="main", pass_chat_data=True))

    for s in OTHER_BOOBS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(
                fed_by_instrument_menu, pattern=s, pass_chat_data=True))
    for s in BOOBS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(
                position_menu, pattern=s, pass_chat_data=True))
    for s in POSITIONS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(time_menu, pattern=s, pass_chat_data=True))
    for s in FEEDING_AMOUNTS:
        updater.dispatcher.add_handler(
            CallbackQueryHandler(
                time_menu, pattern=str(s), pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(
            askfeedinglength_menu, pattern="time", pass_chat_data=True))
    updater.dispatcher.add_handler(
        CallbackQueryHandler(
            submit_duration_menu, pattern="duration", pass_chat_data=True))
    updater.dispatcher.add_handler(CommandHandler('help', help))
    updater.dispatcher.add_error_handler(error)

    # add handlers

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT

    updater.start_webhook(listen="0.0.0.0", port=PORT, url_path=TOKEN)
    updater.bot.set_webhook(URL + "/" + TOKEN)
    updater.idle()


if __name__ == '__main__':
    main()
