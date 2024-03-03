import datetime
import re


class Gregorian:

    def __init__(self, *date):
        if len(date) == 1:
            date = date[0]
            if type(date) is str:
                m = re.match(r'^(\d{4})\D(\d{1,2})\D(\d{1,2})$', date)
                if m:
                    [year, month, day] = [int(m.group(1)), int(m.group(2)), int(m.group(3))]
                else:
                    raise Exception("Invalid Input String")
            elif type(date) is datetime.date:
                [year, month, day] = [date.year, date.month, date.day]
            elif type(date) is tuple:
                year, month, day = date
                year = int(year)
                month = int(month)
                day = int(day)
            else:
                raise Exception("Invalid Input Type")
        elif len(date) == 3:
            year = int(date[0])
            month = int(date[1])
            day = int(date[2])
        else:
            raise Exception("Invalid Input")
        try:
            datetime.datetime(year, month, day)
        except:
            raise Exception("Invalid Date")

        self.gregorian_year = year
        self.gregorian_month = month
        self.gregorian_day = day
        d_4 = year % 4
        g_a = [0, 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
        doy_g = g_a[month] + day
        if d_4 == 0 and month > 2:
            doy_g += 1
        d_33 = int(((year - 16) % 132) * .0305)
        a = 286 if (d_33 == 3 or d_33 < (d_4 - 1) or d_4 == 0) else 287
        if (d_33 == 1 or d_33 == 2) and (d_33 == d_4 or d_4 == 1):
            b = 78
        else:
            b = 80 if (d_33 == 3 and d_4 == 0) else 79
        if int((year - 10) / 63) == 30:
            a -= 1
            b += 1
        if doy_g > b:
            jy = year - 621
            doy_j = doy_g - b
        else:
            jy = year - 622
            doy_j = doy_g + a
        if doy_j < 187:
            jm = int((doy_j - 1) / 31)
            jd = doy_j - (31 * jm)
            jm += 1
        else:
            jm = int((doy_j - 187) / 30)
            jd = doy_j - 186 - (jm * 30)
            jm += 7
        self.persian_year = jy
        self.persian_month = jm
        self.persian_day = jd

    def persian_tuple(self):
        return self.persian_year, self.persian_month, self.persian_day

    def persian_string(self, date_format="{}-{}-{}"):
        return date_format.format(self.persian_year, self.persian_month, self.persian_day)


class Persian:

    def __init__(self, *date):
        if len(date) == 1:
            date = date[0]
            if type(date) is str:
                m = re.match(r'^(\d{4})\D(\d{1,2})\D(\d{1,2})$', date)
                if m:
                    [year, month, day] = [int(m.group(1)), int(m.group(2)), int(m.group(3))]
                else:
                    raise Exception("Invalid Input String")
            elif type(date) is tuple:
                year, month, day = date
                year = int(year)
                month = int(month)
                day = int(day)
            else:
                raise Exception("Invalid Input Type")
        elif len(date) == 3:
            year = int(date[0])
            month = int(date[1])
            day = int(date[2])
        else:
            raise Exception("Invalid Input")
        if year < 1 or month < 1 or month > 12 or day < 1 or day > 31 or (month > 6 and day == 31):
            raise Exception("Incorrect Date")

        self.persian_year = year
        self.persian_month = month
        self.persian_day = day
        d_4 = (year + 1) % 4
        if month < 7:
            doy_j = ((month - 1) * 31) + day
        else:
            doy_j = ((month - 7) * 30) + day + 186
        d_33 = int(((year - 55) % 132) * .0305)
        a = 287 if (d_33 != 3 and d_4 <= d_33) else 286
        if (d_33 == 1 or d_33 == 2) and (d_33 == d_4 or d_4 == 1):
            b = 78
        else:
            b = 80 if (d_33 == 3 and d_4 == 0) else 79
        if int((year - 19) / 63) == 20:
            a -= 1
            b += 1
        if doy_j <= a:
            gy = year + 621
            gd = doy_j + b
        else:
            gy = year + 622
            gd = doy_j - a
        for gm, v in enumerate([0, 31, 29 if (gy % 4 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]):
            if gd <= v:
                break
            gd -= v

        self.gregorian_year = gy
        self.gregorian_month = gm
        self.gregorian_day = gd

    def gregorian_tuple(self):
        return self.gregorian_year, self.gregorian_month, self.gregorian_day

    def gregorian_string(self, date_format="{}-{}-{}"):
        return date_format.format(self.gregorian_year, self.gregorian_month, self.gregorian_day)

    def gregorian_datetime(self):
        return datetime.date(self.gregorian_year, self.gregorian_month, self.gregorian_day)
