from configparser import ConfigParser


class Parameters:

    def __init__(self):
        self.imgsz = 640
        self.conf_thres = 0.25
        self.max_det = 1000
        self.hide_conf = True

        self.region_threshold = 0.05

        self.color_blue = (255, 255, 0)
        self.color_red = (25, 20, 240)
        self.color = self.color_blue
        self.text_x_align = 10
        self.inference_time_y = 30
        self.fps_y = 90
        self.analysis_time_y = 60
        self.font_scale = 0.7
        self.thickness = 2
        self.rect_thickness = 3

        self.rect_size = 15000

        self.pred_shape = (480, 640, 3)
        self.vis_shape = (800, 600)

        config_object = ConfigParser()
        config_object.read("./config.ini")

        dbconfig = config_object["DATABASE"]
        self.dbEntries = dbconfig["dbentries"]
        self.dbResidents = dbconfig["dbresidents"]
        modelconfig = config_object["MODELCONFIG"]
        self.modelPlate_path = modelconfig["platemodel"]
        self.modelCharX_path = modelconfig["charmodel"]
        sourceConfig = config_object["SOURCEDETECT"]
        self.video = sourceConfig["video"]
        self.rtps = sourceConfig["rtps"]
        self.webcam = sourceConfig["webcam"]
        self.source = sourceConfig["source"]
        # services
        external_service_config = config_object["EXTERNAL-SERVICE"]
        self.external_service_url = external_service_config["url"]

        self.video_path = r"./anpr_video.mp4"
        self.cpu_or_cuda = "cpu"  # choose device; "cpu" or "cuda"(if cuda is available)

        self.label_map = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'D', 'Gh', 'H', 'J', 'L', 'M',
                          'N',
                          'P',
                          'PuV', 'PwD', 'Sad', 'Sin', 'T', 'Taxi', 'V', 'Y']

        self.char_dict = {'0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8',
                          '9': '9',
                          'A': '10', 'B': '11', 'P': '12', 'Taxi': '13', 'ث': '14', 'J': '15', 'چ': '16', 'ح': '17',
                          'خ': '18',
                          'D': '19', 'ذ': '20', 'ر': '21', 'ز': '22', 'ژ': '23', 'Sin': '24', 'ش': '25', 'Sad': '26',
                          'ض': '27',
                          'T': '28', 'ظ': '29', 'PuV': '30', 'غ': '31', 'ف': '32', 'Gh': '33', 'ک': '34', 'گ': '35',
                          'L': '36',
                          'M': '37', 'N': '38', 'H': '39', 'V': '40', 'Y': '41', 'PwD': '42'}

        self.char_id_dict = {v: k for k, v in self.char_dict.items()}

        self.alphabetP = {
            "ZERO": "۰",
            "ONE": "۱",
            "TWO": "۲",
            "THREE": "۳",
            "FOUR": "۴",
            "FIVE": "۵",
            "SIX": "۶",
            "SEVEN": "۷",
            "EIGHT": "۸",
            "NINE": "۹",
            "A": "آ",
            "B": "ب",
            "D": "د",
            "Gh": "ق",
            "H": "ه",
            "J": "ج",
            "L": "ل",
            "M": "م",
            "N": "ن",
            "P": "پ",
            "PuV": "ع",
            "PwD": "ژ",
            "Sad": "ص",
            "Sin": "س",
            "T": "ط",
            "Taxi": "ت",
            "V": "و",
            "Y": "ی",
        }

        self.alphabetP2 = {
            "0": "۰",
            "1": "۱",
            "2": "۲",
            "3": "۳",
            "4": "۴",
            "5": "۵",
            "6": "۶",
            "7": "۷",
            "8": "۸",
            "9": "۹",
            "A": "آ",
            "B": "ب",
            "D": "د",
            "Gh": "ق",
            "H": "ه",
            "J": "ج",
            "L": "ل",
            "M": "م",
            "N": "ن",
            "P": "پ",
            "PuV": "ع",
            "PwD": "ژ",
            "Sad": "ص",
            "Sin": "س",
            "T": "ط",
            "Taxi": "ت",
            "V": "و",
            "Y": "ی",
        }

        self.alphabetE = {
            "ZERO": "0",
            "ONE": "1",
            "TWO": "2",
            "THREE": "3",
            "FOUR": "4",
            "FIVE": "5",
            "SIX": "6",
            "SEVEN": "7",
            "EIGHT": "8",
            "NINE": "9",
            'ALEF': 'A',
            'BEH': 'B',
            'DAL': 'D',
            'QAF': 'Gh',
            'HEH': 'H',
            'JEEM': 'J',
            'LAM': 'L',
            'MEEM': 'M',
            'NOON': 'N',
            'PEH': 'P',
            'AIN': 'PuV',
            'JEH': 'PwD',
            'SAD': 'Sad',
            'SEEN': 'Sin',
            'TAH': 'T',
            'TEH': 'Taxi',
            'WAW': 'V',
            'YEH': 'Y',
        }

        self.plateAlphabet = {
            "A": "آ",
            "B": "ب",
            "D": "د",
            "Gh": "ق",
            "H": "ه",
            "J": "ج",
            "L": "ل",
            "M": "م",
            "N": "ن",
            "P": "پ",
            "PuV": "ع",
            "PwD": "ژ",
            "Sad": "ص",
            "Sin": "س",
            "T": "ط",
            "Taxi": "ت",
            "V": "و",
            "Y": "ی",
        }

        self.fieldNames = {
            'fName': 'نام',
            'lName': 'نام خانوادگی',
            'building': 'ساختمان',
            'block': 'بلوک',
            'num': 'پلاک',
            'carModel': 'نوع خودرو',
            'plateNum': 'پلاک خودرو',
            'status': 'مجوز',
            'time': 'ساعت',
            'date': 'تاریخ',
            'platePic': 'عکس پلاک',
            'charPercent': 'درصد حروف',
            'platePercent': 'درصد پلاک',
            'editBtn': 'ویرایش',
            'deleteBtn': 'حذف',
            'searchBtn': 'جستجو',
            'findEntriesBtn': 'ترددها',
            'moreInfo': 'نمایش اطلاعات',
            'addNew': 'ثبت پلاک',
        }

        self.fieldStatus = {
            '0': 'غیر مجاز',
            '1': 'مجاز',
            '2': 'ثبت نشده'
        }

        self.fieldRecordType = {
            '0': 'سیستمی',
            '1': 'دستی',
            '2': 'ویرایش شده'
        }


def getFieldNames(fieldsList):
    params = Parameters()
    fieldNamesOutput = []
    for value in fieldsList:
        fieldNamesOutput.append(params.fieldNames[value])
    return fieldNamesOutput
