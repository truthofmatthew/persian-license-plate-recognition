def type_persian(value):
    splitv = value.split(" ")
    i = 0
    while i < len(splitv):
        if splitv[i] == "":
            splitv[i] = ""
            splitv.remove("")
        elif splitv[i] == " ":
            splitv[i] = " "
            splitv.remove(" ")
        elif " " in splitv[i]:
            splitv[i] = " "
            splitv[i] = "#$#$#$#$#|"
            splitv.remove("#$#$#$#$#|")
        i = i + 1
    b = 0
    while b < len(splitv):
        q = 0
        word = ""
        lastw = ""
        splitv[b] = splitv[b]
        for txt in splitv[b]:
            q = q + 1
            if lastw == "":
                if q == 1:
                    txt = checker_do_not_use(txt, "start")
                elif q == len(splitv[b]):
                    txt = checker_do_not_use(txt, "end")
                elif q > len(splitv[b]):
                    txt = checker_do_not_use(txt, "end")
                else:
                    txt = checker_do_not_use(txt, "center")

            else:
                if q == 1:
                    txt = checker_do_not_use(txt, "start")
                elif q == len(splitv[b]):
                    if "ا" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "آ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "د" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ذ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ر" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ز" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ژ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "و" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    else:
                        txt = checker_do_not_use(txt, "end")
                elif q > len(splitv[b]):
                    if "ا" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "آ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "د" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ذ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ر" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ز" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "ژ" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    elif "و" in lastw:
                        txt = checker_do_not_use(txt, "endPlus")
                    else:
                        txt = checker_do_not_use(txt, "end")
                else:
                    if "ا" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "آ" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "د" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "ذ" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "ر" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "ز" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "ژ" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    elif "و" in lastw:
                        txt = checker_do_not_use(txt, "start")
                    else:
                        txt = checker_do_not_use(txt, "center")
            lastw = txt
            word = word + txt
        word = word[::-1]
        splitv[b] = word
        b = b + 1
    l = len(splitv)
    all_txt = ""
    while 0 < l:
        m = l - 1
        all_txt = all_txt + splitv[m] + " "
        l = l - 1
    editor = all_txt
    editor = editor[::-1]
    editor = editor.replace(" ", "", 1)
    editor = editor[::-1]
    all_txt = editor
    return all_txt


def checker_do_not_use(string, value):
    if (value == "start"):
        string = string.replace("ا", "ﺍ")
        string = string.replace("آ", "ﺁ")
        string = string.replace("ب", "ﺑ")
        string = string.replace("پ", "ﭘ")
        string = string.replace("ت", "ﺗ")
        string = string.replace("ث", "ﺛ")
        string = string.replace("ج", "ﺟ")
        string = string.replace("چ", "ﭼ")
        string = string.replace("ح", "ﺣ")
        string = string.replace("خ", "ﺧ")
        string = string.replace("د", "ﺩ")
        string = string.replace("ذ", "ﺫ")
        string = string.replace("ر", "ﺭ")
        string = string.replace("ز", "ﺯ")
        string = string.replace("ژ", "ﮊ")
        string = string.replace("س", "ﺳ")
        string = string.replace("ش", "ﺷ")
        string = string.replace("ص", "ﺻ")
        string = string.replace("ض", "ﺿ")
        string = string.replace("ط", "ﻃ")
        string = string.replace("ظ", "ﻇ")
        string = string.replace("ع", "ﻋ")
        string = string.replace("غ", "ﻏ")
        string = string.replace("ف", "ﻓ")
        string = string.replace("ق", "ﻗ")
        string = string.replace("ک", "ﮐ")
        string = string.replace("گ", "ﮔ")
        string = string.replace("ل", "ﻟ")
        string = string.replace("م", "ﻣ")
        string = string.replace("ن", "ﻧ")
        string = string.replace("و", "ﻭ")
        string = string.replace("ه", "ﻫ")
        string = string.replace("ی", "ﯾ")
    elif (value == "center"):
        string = string.replace("ا", "ﺎ")
        string = string.replace("آ", "ﺁ")
        string = string.replace("ب", "ﺒ")
        string = string.replace("پ", "ﭙ")
        string = string.replace("ت", "ﺘ")
        string = string.replace("ث", "ﺜ")
        string = string.replace("ج", "ﺠ")
        string = string.replace("چ", "ﭽ")
        string = string.replace("ح", "ﺤ")
        string = string.replace("خ", "ﺨ")
        string = string.replace("د", "ﺪ")
        string = string.replace("ذ", "ﺬ")
        string = string.replace("ر", "ﺮ")
        string = string.replace("ز", "ﺰ")
        string = string.replace("ژ", "ﮋ")
        string = string.replace("س", "ﺴ")
        string = string.replace("ش", "ﺸ")
        string = string.replace("ص", "ﺼ")
        string = string.replace("ض", "ﻀ")
        string = string.replace("ط", "ﻄ")
        string = string.replace("ظ", "ﻈ")
        string = string.replace("ع", "ﻌ")
        string = string.replace("غ", "ﻐ")
        string = string.replace("ف", "ﻔ")
        string = string.replace("ق", "ﻘ")
        string = string.replace("ک", "ﮑ")
        string = string.replace("گ", "ﮕ")
        string = string.replace("ل", "ﻠ")
        string = string.replace("م", "ﻤ")
        string = string.replace("ن", "ﻨ")
        string = string.replace("و", "ﻮ")
        string = string.replace("ه", "ﻬ")
        string = string.replace("ی", "ﯿ")
    elif (value == "end"):
        string = string.replace("ا", "ﺍ")
        string = string.replace("آ", "ﺁ")
        string = string.replace("ب", "ﺐ")
        string = string.replace("پ", "ﭗ")
        string = string.replace("ت", "ﺖ")
        string = string.replace("ث", "ﺚ")
        string = string.replace("ج", "ﺞ")
        string = string.replace("چ", "ﭻ")
        string = string.replace("ح", "ﺢ")
        string = string.replace("خ", "ﺦ")
        string = string.replace("د", "ﺩ")
        string = string.replace("ذ", "ﺫ")
        string = string.replace("ر", "ﺭ")
        string = string.replace("ز", "ﺯ")
        string = string.replace("ژ", "ژ")
        string = string.replace("س", "ﺲ")
        string = string.replace("ش", "ﺶ")
        string = string.replace("ص", "ﺺ")
        string = string.replace("ض", "ﺾ")
        string = string.replace("ط", "ﻂ")
        string = string.replace("ظ", "ﻆ")
        string = string.replace("ع", "ﻊ")
        string = string.replace("غ", "ﻎ")
        string = string.replace("ف", "ﻒ")
        string = string.replace("ق", "ﻖ")
        string = string.replace("ک", "ﮏ")
        string = string.replace("گ", "ﮓ")
        string = string.replace("ل", "ﻞ")
        string = string.replace("م", "م")
        string = string.replace("ن", "ﻥ")
        string = string.replace("و", "ﻭ")
        string = string.replace("ه", "ﻩ")
        string = string.replace("ی", "ﯼ")
    elif (value == "endPlus"):
        string = string.replace("ا", "ﺍ")
        string = string.replace("آ", "ﺁ")
        string = string.replace("ب", "ب")
        string = string.replace("پ", "پ")
        string = string.replace("ت", "ت")
        string = string.replace("ث", "ث")
        string = string.replace("ج", "ج")
        string = string.replace("چ", "چ")
        string = string.replace("ح", "ح")
        string = string.replace("خ", "خ")
        string = string.replace("د", "د")
        string = string.replace("ذ", "ذ")
        string = string.replace("ر", "ر")
        string = string.replace("ز", "ز")
        string = string.replace("ژ", "ژ")
        string = string.replace("س", "س")
        string = string.replace("ش", "ش")
        string = string.replace("ص", "ص")
        string = string.replace("ض", "ض")
        string = string.replace("ط", "ط")
        string = string.replace("ظ", "ظ")
        string = string.replace("ع", "ع")
        string = string.replace("غ", "غ")
        string = string.replace("ف", "ف")
        string = string.replace("ق", "ق")
        string = string.replace("ک", "ک")
        string = string.replace("گ", "گ")
        string = string.replace("ل", "ل")
        string = string.replace("م", "م")
        string = string.replace("ن", "ن")
        string = string.replace("و", "و")
        string = string.replace("ه", "ه")
        string = string.replace("ی", "ی")
    return string
