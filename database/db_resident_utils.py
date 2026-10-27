import sqlite3
from contextlib import contextmanager

from configParams import Parameters
from database.classResidents import Resident

params = Parameters()

fieldsList = ['fName', 'lName', 'building', 'block', 'num', 'carModel', 'plateNum', 'status']
dbResidents = params.dbResidents

SCHEMA = """CREATE TABLE IF NOT EXISTS residents (
                fName TEXT,
                lName TEXT,
                building INTEGER
                ,block INTEGER
                ,num INTEGER
                ,carModel TEXT
                ,plateNum VARCHAR(12) NOT NULL,
                status INTEGER,
                UNIQUE(plateNum))"""


@contextmanager
def _db():
    con = sqlite3.connect(dbResidents)
    try:
        con.execute(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def _one(sql, args):
    with _db() as con:
        cur = con.execute(sql, args)
        row = cur.fetchone()
        return None if row is None else dict(zip([c[0] for c in cur.description], row))


def insertResident(resident, update=False, editingPlate=''):
    try:
        with _db() as con:
            if update:
                con.execute("""UPDATE residents SET fName = :fName, lName = :lName, building = :building, block = :block,
                               num = :num, carModel = :carModel, plateNum = :plateNum, status = :status
                               WHERE plateNum = :editingPlate""", dict(vars(resident), editingPlate=editingPlate))
            else:
                con.execute("INSERT OR IGNORE INTO residents VALUES (:fName, :lName, :building, :block, :num, :carModel, :plateNum, :status)",
                            vars(resident))
    except sqlite3.Error as error:
        print("Failed to update sqlite table", error)


def dbRemoveResident(plateNumber):
    with _db() as con:
        con.execute("DELETE FROM residents WHERE plateNum = ?", (plateNumber,))


def dbGetPlateExist(plateNumber):
    return _one("SELECT status FROM residents WHERE plateNum = ?", (plateNumber,)) is not None


def db_get_plate_status(plateNumber):
    row = _one("SELECT status FROM residents WHERE plateNum = ?", (plateNumber,))
    return 2 if row is None else row['status']


def db_get_plate_owner_name(plateNumber):
    row = _one("SELECT fName, lName FROM residents WHERE plateNum = ?", (plateNumber,))
    return None if row is None else '{} {}'.format(row['fName'], row['lName'])


def dbGetResidentDatasByPlate(plateNumber):
    row = _one("SELECT * FROM residents WHERE plateNum = ?", (plateNumber,))
    return None if row is None else Resident(**row)


def dbGetResidentDatasBylName(lName):
    row = _one("SELECT * FROM residents WHERE lName LIKE ?", (f'%{lName}%',))
    return None if row is None else Resident(**row)


def dbGetAllResidents(limit=100, orderBy='lName', orderType='ASC', whereLike=''):
    if orderBy not in fieldsList or str(orderType).upper() not in ('ASC', 'DESC'):
        raise ValueError(f'bad ORDER BY: {orderBy!r} {orderType!r}')  # identifiers can't be bound, so whitelist
    with _db() as con:
        cur = con.execute(f"SELECT * FROM residents WHERE lName LIKE ? ORDER BY {orderBy} {orderType.upper()} LIMIT ?",
                          (f'%{whereLike}%', int(limit)))
        cols = [c[0] for c in cur.description]
        return [Resident(**dict(zip(cols, row))) for row in cur.fetchall()]
