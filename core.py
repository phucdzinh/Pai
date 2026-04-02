import unicodedata
import time
import threading
import queue
from collections import deque
from pynput.keyboard import Key, Controller, Listener as KeyboardListener
from pynput.mouse import Listener as MouseListener

INPUT_METHOD = 'TELEX'
CHARSET = 'UNICODE'

BASE_VOWELS = ['a', 'ă', 'â', 'e', 'ê', 'i', 'o', 'ô', 'ơ', 'u', 'ư', 'y']
TONES = ['', '\u0301', '\u0300', '\u0309', '\u0303', '\u0323']#Ngang, Sắc, Huyền, Hỏi, Ngã, Nặng

# --- TELEX ---
TELEX_TONES = {'s': 1, 'f': 2, 'r': 3, 'x': 4, 'j': 5, 'z': 0}
TELEX_MODIFIERS = {'w', 'a', 'e', 'o', 'd'}

# --- VNI ---
VNI_TONES = {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '0': 0}
VNI_MODIFIERS = {'6', '7', '8', '9'}

def build_vowel_map():
    vmap = {}
    for v in BASE_VOWELS:
        vmap[v] = [unicodedata.normalize('NFC', v + t) for t in TONES]
    return vmap

VOWEL_MAP = build_vowel_map()

# Cấu trúc: Ánh xạ từ Unicode NFC chuẩn sang các bảng mã khác |||| CHARRSET
UNI_CHARS = "a á à ả ã ạ ă ắ ằ ẳ ẵ ặ â ấ ầ ẩ ẫ ậ e é è ẻ ẽ ẹ ê ế ề ể ễ ệ i í ì ỉ ĩ ị o ó ò ỏ õ ọ ô ố ồ ổ ỗ ộ ơ ớ ờ ở ỡ ợ u ú ù ủ ũ ụ ư ứ ừ ử ữ ự y ý ỳ ỷ ỹ ỵ đ Đ"
VNI_CHARS = "a aù aø aû aõ aï aê aé aè aë aö añ aâ aá aà aä aã aö e eù eø eû eõ eï eâ eá eà eä eã eö i iù iø iû iõ iï o où oø oû oõ oï oâ oá oà oä oã oö oê oé oè oë oö oñ u uù uø uû uõ uï uö uù uø uû uõ uï y yù yø yû yõ yï ñ Ñ"
TCVN3_CHARS="a ¸ µ ¶ · ¹ ¨ ¾ » ¼ ½ Æ © Ê Ç È É Ë e Ð Ì Î Ï Ñ ê Õ Ò Ó Ô Ö i Ý × Ø Ü Þ o á ß à ã ä ô è å æ ç é ơ í ê ë ì î u ó ï ñ ò õ ư ø ö ÷ ù ú y ý ú û ü þ đ Đ"

def build_charset_map(source_str, target_str):
    src = source_str.split()
    tgt = target_str.split()
    cmap = {}
    for i in range(len(src)):
        if i < len(tgt): cmap[src[i]] = tgt[i]
        upper_src = src[i].upper()
        if upper_src not in cmap:
            if target_str == VNI_CHARS:
                cmap[upper_src] = tgt[i][0].upper() + tgt[i][1:]
            else:
                cmap[upper_src] = tgt[i].upper() 
    return cmap

MAP_VNI_WIN = build_charset_map(UNI_CHARS, VNI_CHARS)
MAP_TCVN3 = build_charset_map(UNI_CHARS, TCVN3_CHARS)


class VietnameseEngine:
    def __init__(self, input_method='TELEX', charset='UNICODE'):
        self.keyboard = Controller()
        self.buffer = []
        self.display_word = ""
        self.input_method = input_method.upper()
        self.charset = charset.upper()
        
        self.tones = TELEX_TONES if self.input_method == 'TELEX' else VNI_TONES
        self.modifiers = TELEX_MODIFIERS if self.input_method == 'TELEX' else VNI_MODIFIERS

        self.lock = threading.Lock()
        self.simulated_backspaces = 0
        self.simulated_chars = deque()
        self.typing_queue = queue.Queue()
        threading.Thread(target=self._typing_worker, daemon=True).start()

    def reset_state(self):
        with self.lock:
            self.buffer.clear()
            self.display_word = ""
            self.simulated_backspaces = 0
            self.simulated_chars.clear()

    def get_base_char_and_tone(self, char):
        c_low = char.lower()
        for base, tones in VOWEL_MAP.items():
            if c_low in tones: return base, tones.index(c_low)
        return c_low, 0

    def apply_modifier_telex(self, chars, mod_key):
        mod_key = mod_key.lower()
        if mod_key == 'd':
            for i in range(len(chars)-1, -1, -1):
                c_low = chars[i].lower()
                if c_low == 'd': chars[i] = 'Đ' if chars[i].isupper() else 'đ'; return True
                elif c_low == 'đ': chars[i] = 'D' if chars[i].isupper() else 'd'; return "UNDO"
            return False

        if mod_key == 'w':
            for i in range(len(chars)-1):
                b1, t1 = self.get_base_char_and_tone(chars[i])
                b2, t2 = self.get_base_char_and_tone(chars[i+1])
                if b1 == 'u' and b2 == 'o':
                    chars[i] = VOWEL_MAP['ư'][t1].upper() if chars[i].isupper() else VOWEL_MAP['ư'][t1]
                    chars[i+1] = VOWEL_MAP['ơ'][t2].upper() if chars[i+1].isupper() else VOWEL_MAP['ơ'][t2]
                    return True
                elif b1 == 'ư' and b2 == 'ơ': 
                    chars[i] = VOWEL_MAP['u'][t1].upper() if chars[i].isupper() else VOWEL_MAP['u'][t1]
                    chars[i+1] = VOWEL_MAP['o'][t2].upper() if chars[i+1].isupper() else VOWEL_MAP['o'][t2]
                    return "UNDO"

        for i in range(len(chars)-1, -1, -1):
            base, tone = self.get_base_char_and_tone(chars[i])
            is_upper = chars[i].isupper()
            new_base = base
            is_undo = False

            if mod_key in ['a', 'e', 'o'] and i != len(chars) - 1: break 

            if mod_key == 'w':
                if base == 'u': new_base = 'ư'
                elif base == 'o': new_base = 'ơ'
                elif base == 'a': new_base = 'ă'
                elif base in ['ư', 'ơ', 'ă']: new_base = {'ư':'u', 'ơ':'o', 'ă':'a'}[base]; is_undo = True
            elif mod_key == 'a':
                if base in ['a', 'ă']: new_base = 'â'
                elif base == 'â': new_base = 'a'; is_undo = True
            elif mod_key == 'e':
                if base == 'e': new_base = 'ê'
                elif base == 'ê': new_base = 'e'; is_undo = True
            elif mod_key == 'o':
                if base in ['o', 'ơ']: new_base = 'ô'
                elif base == 'ô': new_base = 'o'; is_undo = True

            if new_base != base:
                new_char = VOWEL_MAP[new_base][tone]
                chars[i] = new_char.upper() if is_upper else new_char
                return "UNDO" if is_undo else True
        return False

    def apply_modifier_vni(self, chars, mod_key):
        if mod_key == '9':
            for i in range(len(chars)-1, -1, -1):
                c_low = chars[i].lower()
                if c_low == 'd': chars[i] = 'Đ' if chars[i].isupper() else 'đ'; return True
                elif c_low == 'đ': chars[i] = 'D' if chars[i].isupper() else 'd'; return "UNDO"
            return False

        for i in range(len(chars)-1, -1, -1):
            base, tone = self.get_base_char_and_tone(chars[i])
            is_upper = chars[i].isupper()
            new_base = base
            is_undo = False

            if mod_key == '6':
                if base in ['a', 'ă']: new_base = 'â'
                elif base == 'e': new_base = 'ê'
                elif base in ['o', 'ơ']: new_base = 'ô'
                elif base in ['â', 'ê', 'ô']: 
                    new_base = {'â':'a', 'ê':'e', 'ô':'o'}[base]; is_undo = True
            elif mod_key == '7':
                if base == 'o': new_base = 'ơ'
                elif base == 'u': new_base = 'ư'
                elif base in ['ơ', 'ư']:
                    new_base = {'ơ':'o', 'ư':'u'}[base]; is_undo = True
            elif mod_key == '8':
                if base == 'a': new_base = 'ă'
                elif base == 'ă': new_base = 'a'; is_undo = True

            if new_base != base:
                new_char = VOWEL_MAP[new_base][tone]
                chars[i] = new_char.upper() if is_upper else new_char
                return "UNDO" if is_undo else True
        return False

    def find_tone_placement(self, chars):
        word = "".join(chars).lower()
        vowel_indices = []
        for i, c in enumerate(word):
            base, _ = self.get_base_char_and_tone(c)
            if base in BASE_VOWELS: vowel_indices.append(i)

        if not vowel_indices: return -1
        if len(vowel_indices) == 1: return vowel_indices[0]

        last_char_base, _ = self.get_base_char_and_tone(word[-1])
        ends_with_consonant = last_char_base not in BASE_VOWELS

        if word.startswith('qu') and len(vowel_indices) > 1 and vowel_indices[0] == 1: return vowel_indices[1]
        if word.startswith('gi') and len(vowel_indices) > 1 and vowel_indices[0] == 1: return vowel_indices[1]

        if ends_with_consonant: return vowel_indices[-1]
        else:
            if len(vowel_indices) == 2:
                v1, v2 = word[vowel_indices[0]].lower(), word[vowel_indices[1]].lower()
                if (v1, v2) in [('o', 'a'), ('o', 'e'), ('u', 'y'), ('u', 'ê')]: return vowel_indices[1]
                return vowel_indices[0]
            return vowel_indices[-2] if len(vowel_indices) >= 2 else vowel_indices[0]

    def apply_tone(self, chars, target_tone):
        clean_chars = []
        current_tone = 0
        for c in chars:
            b, t = self.get_base_char_and_tone(c)
            if t != 0: current_tone = t
            clean_chars.append(b.upper() if c.isupper() else b)

        if target_tone == current_tone or target_tone == 0: 
            return clean_chars, (target_tone == current_tone)

        target_idx = self.find_tone_placement(clean_chars)
        if target_idx != -1 and target_idx < len(clean_chars):
            c = clean_chars[target_idx]
            b, _ = self.get_base_char_and_tone(c)
            if b in VOWEL_MAP:
                new_c = VOWEL_MAP[b][target_tone]
                clean_chars[target_idx] = new_c.upper() if c.isupper() else new_c
                
        return clean_chars, False

    def normalize_word_tone(self, chars):
        current_tone = 0
        clean_chars = []
        for c in chars:
            b, t = self.get_base_char_and_tone(c)
            if t != 0: current_tone = t
            clean_chars.append(b.upper() if c.isupper() else b)

        if current_tone == 0: return chars
        target_idx = self.find_tone_placement(clean_chars)
        if target_idx != -1 and target_idx < len(clean_chars):
            c = clean_chars[target_idx]
            b, _ = self.get_base_char_and_tone(c)
            if b in VOWEL_MAP:
                new_c = VOWEL_MAP[b][current_tone]
                clean_chars[target_idx] = new_c.upper() if c.isupper() else new_c
        return clean_chars

    def apply_charset(self, unicode_string):
        if self.charset == 'UNICODE': return unicode_string
        
        target_map = MAP_VNI_WIN if self.charset == 'VNI_WIN' else MAP_TCVN3
        result = ""
        for char in unicode_string:
            result += target_map.get(char, char)
        return result

    def process(self, raw_buffer):
        if not raw_buffer: return ""
        result_chars = []
        
        for char in raw_buffer:
            c_low = char.lower()
            applied = False
            
            if c_low in self.tones:
                test_chars, is_undo = self.apply_tone(result_chars.copy(), self.tones[c_low])
                if is_undo:
                    result_chars = test_chars; result_chars.append(char); applied = True
                elif "".join(test_chars) != "".join(result_chars):
                    result_chars = test_chars; applied = True
                        
            elif c_low in self.modifiers:
                backup = result_chars.copy()
                if self.input_method == 'TELEX':
                    state = self.apply_modifier_telex(result_chars, c_low)
                else:
                    state = self.apply_modifier_vni(result_chars, c_low)

                if state is True: applied = True
                elif state == "UNDO": result_chars.append(char); applied = True
                else: result_chars = backup

            if not applied:
                result_chars.append(char)

        result_chars = self.normalize_word_tone(result_chars)
        unicode_result = unicodedata.normalize('NFC', "".join(result_chars))
        return self.apply_charset(unicode_result)

    def calculate_delta(self, old_str, new_str):
        i = 0
        while i < len(old_str) and i < len(new_str) and old_str[i] == new_str[i]: i += 1
        return len(old_str) - i, new_str[i:]

    def _typing_worker(self):
        while True:
            task = self.typing_queue.get()
            if task is None: continue
            backspaces, to_type = task
            
            with self.lock:
                self.simulated_backspaces += backspaces
                self.simulated_chars.extend(list(to_type))

            for _ in range(backspaces):
                self.keyboard.press(Key.backspace)
                self.keyboard.release(Key.backspace)
                time.sleep(0.002)

            for char in to_type:
                self.keyboard.press(char)
                self.keyboard.release(char)
                time.sleep(0.002)

    def on_press(self, key):
        with self.lock:
            if key == Key.backspace and self.simulated_backspaces > 0:
                self.simulated_backspaces -= 1; return
            try:
                char = key.char
                if char and self.simulated_chars and char == self.simulated_chars[0]:
                    self.simulated_chars.popleft(); return
            except AttributeError: pass

        if key == Key.backspace:
            if self.buffer:
                self.buffer.pop()
                new_word = self.process(self.buffer)
                expected_screen = self.display_word[:-1] 
                if new_word != expected_screen:
                    backspaces, to_type = self.calculate_delta(expected_screen, new_word)
                    self.typing_queue.put((backspaces, to_type))
                self.display_word = new_word
            return

        if key in [Key.space, Key.enter, Key.tab, Key.esc] or str(key).startswith('Key.'):
            self.reset_state(); return

        try:
            char = key.char

            if self.input_method == 'VNI' and char is not None and char.isdigit():
                pass
            elif char is None or not char.isalpha():
                self.reset_state(); return

            if len(self.buffer) > 25: self.reset_state()

            self.buffer.append(char)
            new_word = self.process(self.buffer)
            
            expected_screen = self.display_word + char
            if new_word != expected_screen:
                backspaces, to_type = self.calculate_delta(expected_screen, new_word)
                self.typing_queue.put((backspaces, to_type))
                
            self.display_word = new_word
        except AttributeError:
            pass

    def on_click(self, x, y, button, pressed):
        if pressed: self.reset_state()

if __name__ == '__main__':
    engine = VietnameseEngine(input_method=INPUT_METHOD, charset=CHARSET)
    mouse_listener = MouseListener(on_click=engine.on_click)
    mouse_listener.start()
    with KeyboardListener(on_press=engine.on_press) as keyboard_listener:
        keyboard_listener.join()