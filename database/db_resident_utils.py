import datetime
import sqlite3
import time

from configParams import Parameters
from database.classResidents import Resident
from helper.text_decorators import convert_persian_to_english, join_elements

params = Parameters()

fieldsList = ['fName', 'lName', 'building', 'block', 'num', 'carModel', 'plateNum', 'status']
dbResidents = params.dbResidents


def insertResident(resident, update=False, editingPlate=''):
    try:
        sqlConnect = sqlite3.connect(dbResidents)
        sqlCursor = sqlConnect.cursor()

        if update:
            pltNum = join_elements(convert_persian_to_english(resident.getPlateNumber()))

            updateResidentSQL = f"""UPDATE
                                residents
                                SET
                                fName = :fName,
                                lName= :lName,
                                building= :building,
                                block= :block,
                                num= :num,
                                carModel= :carModel,
                                plateNum= :plateNum,
                                status = :status
                                WHERE
                                plateNum= :editingPlate"""
            dlist = vars(resident)
            dlist['editingPlate'] = editingPlate
            sqlCursor.execute(updateResidentSQL, dlist)

        else:
            sqlCursor.execute(
                "INSERT OR IGNORE INTO residents VALUES (:fName, :lName, :building, :block, :num, :carModel, :plateNum, :status)",
                vars(resident))

        sqlCursor.close()
    except sqlite3.Error as error:
        print("Failed to update sqlite table", error)

    finally:
        if sqlConnect:
            sqlConnect.commit()
            sqlConnect.close()


def getResidentByName(conn, cur, lastname):
    cur.execute("SELECT * FROM residents WHERE last=:last", {'last': lastname})
    return cur.fetchall()


def updateResident(conn, cur, resident, pay):
    with conn:
        cur.execute("""UPDATE residents SET pay = :pay
                    WHERE first = :first AND last = :last""",
                    {'first': resident.first, 'last': resident.last, 'pay': pay})


def dbRemoveResident(plateNumber):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    removeResidentSQL = f"""DELETE FROM residents WHERE plateNum='{plateNumber}'"""
    removeResident = sqlCursor.execute(removeResidentSQL)
    sqlConnect.commit()
    sqlConnect.close()


def dbGetPlateExist(plateNumber):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    PlateExistSQL = f"""SELECT status FROM residents WHERE plateNum='{plateNumber}'"""
    PlateExist = sqlCursor.execute(PlateExistSQL).fetchone()
    sqlConnect.commit()
    sqlConnect.close()
    if PlateExist is not None:
        return True
    else:
        return False


def db_get_plate_status(plateNumber):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    PlateStatusSQL = f"""SELECT status FROM residents WHERE plateNum='{plateNumber}'"""
    PlateStatus = sqlCursor.execute(PlateStatusSQL).fetchone()
    sqlConnect.commit()
    sqlConnect.close()

    if PlateStatus is not None:
        return PlateStatus[0]
    return 2


def db_get_plate_owner_name(plateNumber):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    OwnerNameSQL = f"""SELECT fName, lName FROM residents WHERE plateNum='{plateNumber}'"""
    OwnerName = sqlCursor.execute(OwnerNameSQL).fetchone()
    sqlConnect.commit()
    sqlConnect.close()
    if OwnerName is not None:
        return '{} {}'.format(OwnerName[0], OwnerName[1])
    return None


def dbGetResidentDatasByPlate(plateNumber):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()

    FullResidentSQL = f"""SELECT * FROM residents WHERE plateNum='{plateNumber}'"""
    FullResident = sqlCursor.execute(FullResidentSQL).fetchall()

    FullData = dict(zip([c[0] for c in sqlCursor.description], FullResident[0]))
    sqlConnect.commit()
    sqlConnect.close()
    if FullResident is not None:
        return Resident(**FullData)
    return None


def dbGetResidentDatasBylName(lName):
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    FullResidentSQL = f"""SELECT * FROM residents WHERE lName LIKE '%{lName}%'"""
    FullResident = sqlCursor.execute(FullResidentSQL).fetchall()
    FullData = dict(zip([c[0] for c in sqlCursor.description], FullResident[0]))
    sqlConnect.commit()
    sqlConnect.close()
    if FullResident is not None:
        return Resident(**FullData)
    return None


def dbGetAllResidents(limit=100, orderBy='lName', orderType='ASC', whereLike=''):
    listAllResidents = []
    sqlConnect = sqlite3.connect(dbResidents)
    sqlCursor = sqlConnect.cursor()
    allResidentSQL = f"""SELECT * FROM residents WHERE lName LIKE '%{whereLike}%' ORDER BY {orderBy} {orderType} LIMIT {limit} """
    allResident = sqlCursor.execute(allResidentSQL).fetchall()
    for i in range(len(allResident)):
        FullData = dict(zip([c[0] for c in sqlCursor.description], allResident[i]))
        listAllResidents.append(Resident(**FullData))
    sqlConnect.commit()
    sqlConnect.close()
    return listAllResidents


similarityTemp = ''


def dbEnteriesTime(number, charConfAvg, plateConfAvg, croppedPlate, status):
    global similarityTemp
    dfReadEnteries = pd.read_csv(str(Path().absolute()) + '/base/enteries.csv')

    isSimilar = similarityChecker(similarityTemp, number)

    if not isSimilar:
        similarityTemp = number
        if True:

            timeNow = datetime.now()
            result = dfReadEnteries[dfReadEnteries['plateNum'] == number]
            if result is not None and not result.empty and number != '':

                inn = result.index.to_list()[len(result.index) - 1]
                strTime = dfReadEnteries.at[dfReadEnteries.index[inn], 'time']
                strDate = dfReadEnteries.at[dfReadEnteries.index[inn], 'date']
                if timeDifference(strTime, strDate):
                    display_time = timeNow.strftime("%H:%M:%S")
                    display_date = timeNow.strftime("%Y-%m-%d")

                    plateImgName = 'temp/{}-{}.jpg'.format(number,
                                                           datetime.now().strftime("%H:%M:%S %Y-%m-%d"))
                    croppedPlate.save(plateImgName, format='jpg')

                    enteriesExport = {'status': [status], 'plateNum': [number], 'time': [display_time],
                                      'date': [display_date]
                        , 'platePic': plateImgName, 'charPercent': [charConfAvg], 'platePercent': [plateConfAvg]
                                      }
                    df = pd.DataFrame(enteriesExport)
                    df.to_csv(str(Path().absolute()) + '/base/enteries.csv', header=False, index=False, mode='a',
                              encoding='utf-8')

                else:
                    pass
            else:
                if number != '':
                    display_time = time.strftime("%H:%M:%S")
                    display_date = time.strftime("%Y-%m-%d")

                    plateImgName = 'temp/{}-{}.jpg'.format(number, datetime.now().strftime("%H:%M:%S-%Y-%m-%d"))
                    croppedPlate.save(plateImgName, format='jpg')

                    enteriesExport = {'status': [status], 'plateNum': [number], 'time': [display_time],
                                      'date': [display_date]
                        , 'platePic': plateImgName, 'charPercent': [charConfAvg], 'platePercent': [plateConfAvg]
                                      }
                    df = pd.DataFrame(enteriesExport)
                    df.to_csv(str(Path().absolute()) + '/base/enteries.csv', header=False, index=False, mode='a',
                              encoding='utf-8')
    else:
        pass


def dbRefreshTable():
    dfReadEnteries = pd.read_csv(str(Path().absolute()) + '/base/enteries.csv')
    dfReadEnteries = dfReadEnteries.iloc[-20:].sort_index(ascending=False)
    return dfReadEnteries


def getFieldNames(fieldsList):
    fieldNamesOutput = []
    for value in fieldsList:
        fieldNamesOutput.append(params.fieldNames[value])
    return fieldNamesOutput


from datetime import datetime


def timeDifference(strTime, strDate):
    start_time = datetime.strptime(strTime + ' ' + strDate, "%H:%M:%S %Y-%m-%d")
    end_time = datetime.strptime(datetime.now().strftime("%H:%M:%S %Y-%m-%d"), "%H:%M:%S %Y-%m-%d")
    delta = end_time - start_time

    sec = delta.total_seconds()
    min = (sec / 60).__ceil__()

    if min > 1:
        return True
    else:
        return False
