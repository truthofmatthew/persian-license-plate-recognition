import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

from configParams import Parameters
from database.classEntries import Entries
from helper.text_decorators import check_similarity_threshold
from services.send import send_data_to_external_service

params = Parameters()

fieldsList = ['platePercent', 'charPercent', 'eDate', 'eTime', 'plateNum', 'status']
dbEntries = params.dbEntries

SCHEMA = """CREATE TABLE IF NOT EXISTS entries (
                platePercent INTEGER
                ,charPercent INTEGER
                ,eDate VARCHAR(25)
                ,eTime VARCHAR(25)
                ,plateNum VARCHAR(20) NOT NULL,
                status INTEGER)"""


@contextmanager
def _db():
    con = sqlite3.connect(dbEntries)
    try:
        con.execute(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _order(orderBy, orderType):
    """Column names and sort direction can't be bound as SQL parameters, so whitelist them."""
    if orderBy not in fieldsList or str(orderType).upper() not in ('ASC', 'DESC'):
        raise ValueError(f'bad ORDER BY: {orderBy!r} {orderType!r}')
    return orderBy, orderType.upper()


def insertEntries(entry):
    with _db() as con:
        con.execute("INSERT OR IGNORE INTO entries VALUES (:platePercent, :charPercent, :eDate, :eTime, :plateNum, :status)",
                    vars(entry))


def dbRemoveEntries(plateNumber):
    with _db() as con:
        con.execute("DELETE FROM entries WHERE plateNum = ?", (plateNumber,))


def dbGetPlateLatestEntry(plateNumber):
    with _db() as con:
        cur = con.execute("SELECT * FROM entries WHERE plateNum = ? ORDER BY eDate DESC, eTime DESC LIMIT 1", (plateNumber,))
        row = cur.fetchone()
        if row is None:
            return None
        return Entries(**dict(zip([c[0] for c in cur.description], row)))


def dbGetAllEntries(limit=10, orderBy='eDate', orderType='DESC', whereLike=''):
    orderBy, orderType = _order(orderBy, orderType)
    with _db() as con:
        cur = con.execute(f"SELECT * FROM entries WHERE plateNum LIKE ? ORDER BY {orderBy} {orderType}, eTime {orderType} LIMIT ?",
                          (f'%{whereLike}%', int(limit)))
        cols = [c[0] for c in cur.description]
        return [Entries(**dict(zip(cols, row))) for row in cur.fetchall()]


similarityTemp = ''


def db_entries_time(number, charConfAvg, plateConfAvg, croppedPlate, status, external_service_data: dict | None = None):
    global similarityTemp
    if number == '' or check_similarity_threshold(similarityTemp, number):
        return
    similarityTemp = number
    result = dbGetPlateLatestEntry(number)
    if result is not None and not timeDifference(result.getTime(), result.getDate(persian=False)):
        return  # same plate logged less than a minute ago
    display_time = time.strftime("%H:%M:%S")
    display_date = time.strftime("%Y-%m-%d")
    os.makedirs('temp', exist_ok=True)  # same name Entries.getPlatePic() builds
    croppedPlate.save(f'temp/{number}_{display_time}_{display_date}.jpg', format='jpg')
    insertEntries(Entries(plateConfAvg, charConfAvg, display_date, display_time, number, status))
    if external_service_data:
        send_data_to_external_service(external_service_data)


def timeDifference(strTime, strDate):
    start_time = datetime.strptime(strTime + ' ' + strDate, "%H:%M:%S %Y-%m-%d")
    return (datetime.now() - start_time).total_seconds() > 60
