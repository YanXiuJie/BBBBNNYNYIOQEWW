import json
import logging
import os
from fractions import Fraction
from itertools import count

import httpx


_generation_counter = count(1)
logger = logging.getLogger(__name__)
GENERIC_SUPPORT_PHRASES = (
    "Soalan ini " + "dipilih supaya " + "kemahiran Matematik Tahun 5 " + "sepadan dengan subtopik.",
    "Kenal pasti kata kunci, " + "operasi dan unit sebelum menjawab.",
    "Pecahkan masalah ini " + "kepada beberapa langkah kecil.",
    "Buat gambar rajah atau tulis " + "langkah-langkah dengan teliti",
    "Cuba ikuti langkah-langkah " + "yang dinyatakan dalam penjelasan",
    "Gunakan kaedah " + "dalam penjelasan",
)


def generate_question_ms(subtopic_title: str, difficulty: str, question_type: str = "short_answer") -> dict:
    llm_question = generate_with_llm(subtopic_title, difficulty, question_type)
    if llm_question:
        return llm_question
    return generate_with_template(subtopic_title, difficulty, question_type)


def generate_with_template(subtopic_title: str, difficulty: str, question_type: str = "short_answer") -> dict:
    index = next(_generation_counter)
    prompt, answer, hint, explanation = build_topic_question(subtopic_title, difficulty, index)
    support_text = build_support_texts(
        subtopic_title=subtopic_title,
        prompt=prompt,
        answer=answer,
        hint=hint,
        explanation=explanation,
    )
    return {
        "difficulty": difficulty,
        "question_type": question_type,
        "prompt_ms": strip_subtopic_prefix(prompt, subtopic_title),
        "expected_answer": answer,
        "options": build_options(answer, index) if question_type == "multiple_choice" else [],
        "hint_ms": support_text["hint_ms"],
        "hint_level2_ms": support_text["hint_level2_ms"],
        "hint_level3_ms": support_text["hint_level3_ms"],
        "explanation_ms": support_text["explanation_ms"],
        "source": "template",
        "validation_status": "validated",
    }


def generate_with_llm(subtopic_title: str, difficulty: str, question_type: str = "short_answer") -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = (
        "Generate one Bahasa Melayu Year 5 mathematics question as JSON with keys "
        "prompt_ms, expected_answer, hint_ms, hint_level2_ms, hint_level3_ms, explanation_ms, options. "
        f"Subtopic: {subtopic_title}. Difficulty: {difficulty}. "
        f"Question type: {question_type}. "
        "If the type is multiple_choice, options must contain 4 concise options including the expected answer. "
        "If the type is short_answer, options must be an empty array. "
        "Use exactly this JSON shape: "
        '{"prompt_ms":"...","expected_answer":"...","hint_ms":"...","hint_level2_ms":"...","hint_level3_ms":"...","explanation_ms":"...","options":["...","...","...","..."]}. '
        "The mathematical skill must match the subtopic exactly; do not reuse generic fraction questions for unrelated topics. "
        "hint_ms must be a useful first clue tied to this exact question without revealing the final answer. "
        "hint_level2_ms must be more specific and name the operation or conversion to use. "
        "hint_level3_ms may be very specific and almost reveal the calculation, but still ask the pupil to finish thinking. "
        "explanation_ms must be a real step-by-step solution in Bahasa Melayu using Langkah 1, Langkah 2 and Langkah 3, with the actual numbers/units from the question and the final answer. "
        "Never use generic support text that only says the question was selected to match the Year 5 subtopic. "
        "Do not start prompt_ms with the subtopic title because the interface displays the subtopic separately. "
        "Keep the answer concise and mathematically checkable. "
        "Return a single JSON object and no markdown."
    )
    try:
        response = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        parsed = json.loads(content)
        answer = str(parsed["expected_answer"])
        support_text = build_support_texts(
            subtopic_title=subtopic_title,
            prompt=str(parsed["prompt_ms"]),
            answer=answer,
            hint=str(parsed.get("hint_ms", "")),
            hint_level2=str(parsed.get("hint_level2_ms", "")),
            hint_level3=str(parsed.get("hint_level3_ms", "")),
            explanation=str(parsed.get("explanation_ms", "")),
        )
        return {
            "difficulty": difficulty,
            "question_type": question_type,
            "prompt_ms": strip_subtopic_prefix(str(parsed["prompt_ms"]), subtopic_title),
            "expected_answer": answer,
            "options": normalize_generated_options(question_type, answer, parsed.get("options", [])),
            "hint_ms": support_text["hint_ms"],
            "hint_level2_ms": support_text["hint_level2_ms"],
            "hint_level3_ms": support_text["hint_level3_ms"],
            "explanation_ms": support_text["explanation_ms"],
            "source": "ai",
            "validation_status": "validated",
        }
    except Exception as exc:
        logger.warning(
            "LLM question generation parse/validation failed for subtopic=%r difficulty=%r type=%r: %s",
            subtopic_title,
            difficulty,
            question_type,
            exc,
        )
        return None


def strip_subtopic_prefix(prompt: str, subtopic_title: str) -> str:
    cleaned = str(prompt).strip()
    prefix = f"{subtopic_title}:"
    if cleaned.casefold().startswith(prefix.casefold()):
        return cleaned[len(prefix):].strip()
    return cleaned


def is_generic_support_text(text: str | None) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return True
    cleaned_lower = cleaned.casefold()
    return any(phrase.casefold() in cleaned_lower for phrase in GENERIC_SUPPORT_PHRASES)


def build_support_texts(
    subtopic_title: str,
    prompt: str,
    answer: str,
    hint: str,
    explanation: str = "",
    hint_level2: str = "",
    hint_level3: str = "",
) -> dict[str, str]:
    hint_ms = str(hint or "").strip()
    if is_generic_support_text(hint_ms):
        hint_ms = build_question_specific_hint(prompt)

    explanation_ms = str(explanation or "").strip()
    if is_generic_support_text(explanation_ms) or "Langkah" not in explanation_ms:
        explanation_ms = build_step_by_step_explanation(subtopic_title, prompt, answer, hint_ms)

    hint_level2_ms = str(hint_level2 or "").strip()
    if is_generic_support_text(hint_level2_ms):
        hint_level2_ms = build_level2_hint(prompt, hint_ms)

    hint_level3_ms = str(hint_level3 or "").strip()
    if is_generic_support_text(hint_level3_ms):
        hint_level3_ms = build_level3_hint(answer, explanation_ms)

    return {
        "hint_ms": hint_ms,
        "hint_level2_ms": hint_level2_ms,
        "hint_level3_ms": hint_level3_ms,
        "explanation_ms": explanation_ms,
    }


def build_question_specific_hint(prompt: str) -> str:
    prompt_summary = summarize_prompt(prompt)
    return f"Fokus pada maklumat dalam soalan ini: {prompt_summary}"


def build_level2_hint(prompt: str, hint: str) -> str:
    prompt_summary = summarize_prompt(prompt)
    return f"Gunakan langkah daripada petunjuk awal untuk soalan ini: {hint.rstrip('.')}. Maklumat utama ialah {prompt_summary}"


def build_level3_hint(answer: str, explanation: str) -> str:
    first_steps = explanation.split("Langkah 3:")[0].strip()
    return f"Ikuti langkah pengiraan itu hingga nilai akhir menjadi {answer}. {first_steps}".strip()


def build_step_by_step_explanation(subtopic_title: str, prompt: str, answer: str, hint: str) -> str:
    prompt_summary = summarize_prompt(prompt)
    hint_text = str(hint or "").strip().rstrip(".")
    subtopic_text = f" bagi subtopik {subtopic_title}" if subtopic_title else ""
    return (
        f"Langkah 1: Baca maklumat soalan{subtopic_text}: {prompt_summary}. "
        f"Langkah 2: Gunakan kaedah yang sesuai: {hint_text}. "
        "Langkah 3: Jalankan pengiraan dengan nombor dan unit yang diberi dalam soalan. "
        f"Langkah 4: Semak semula unit atau format jawapan. Jawapan akhir ialah {answer}."
    )


def summarize_prompt(prompt: str, max_length: int = 180) -> str:
    cleaned = " ".join(str(prompt or "").strip().split())
    if len(cleaned) <= max_length:
        return cleaned.rstrip("?")
    return cleaned[: max_length - 3].rstrip() + "..."


def format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def build_topic_question(subtopic_title: str, difficulty: str, index: int) -> tuple[str, str, str, str]:
    topic = subtopic_title.lower()
    level = difficulty_level(difficulty)
    step = index + level
    hint = "Kenal pasti kata kunci, operasi dan unit sebelum menjawab."
    explanation = ""

    if "simpan" in topic or "labur" in topic:
        amount = 8 + (step * 2)
        months = 3 + level + (index % 4)
        total = amount * months
        if difficulty == "easy":
            return (
                f"Aina menyimpan RM{amount} setiap bulan selama {months} bulan. Berapakah jumlah simpanan Aina?",
                f"RM{total}",
                "Darab jumlah simpanan bulanan dengan bilangan bulan.",
                explanation,
            )
        if difficulty == "medium":
            withdrawal = 5 + (index % 4) * 2
            return (
                f"Aina menyimpan RM{amount} setiap bulan selama {months} bulan, kemudian mengeluarkan RM{withdrawal}. Berapakah baki simpanan?",
                f"RM{total - withdrawal}",
                "Cari jumlah simpanan dahulu, kemudian tolak wang yang dikeluarkan.",
                explanation,
            )
        interest = 4 + (index % 5) * 2
        return (
            f"Aina menyimpan RM{amount} setiap bulan selama {months} bulan dan menerima faedah RM{interest}. Berapakah jumlah akhir simpanan?",
            f"RM{total + interest}",
            "Cari jumlah simpanan dahulu, kemudian tambah faedah.",
            explanation,
        )
    if "faedah" in topic:
        principal = 100 + (step * 20)
        rate = 2 + level
        return (
            f"Simpanan RM{principal} menerima faedah mudah {rate}% setahun. Berapakah faedah selepas 1 tahun?",
            f"RM{principal * rate // 100}",
            "Faedah mudah = modal x kadar x masa.",
            explanation,
        )
    if "kredit" in topic or "hutang" in topic:
        price = 80 + (step * 10)
        paid = 20 + (level * 10)
        return (
            f"Harga barang ialah RM{price}. Murid telah membayar RM{paid}. Berapakah baki hutang?",
            f"RM{price - paid}",
            "Tolak bayaran daripada harga barang.",
            explanation,
        )
    if "wang" in topic or "nilai wang" in topic:
        first = 12 + (step * 3)
        second = 5 + level + (index % 5)
        if "tolak" in topic:
            return (f"RM{first} ditolak RM{second}. Berapakah bakinya?", f"RM{first - second}", hint, explanation)
        if "darab" in topic:
            return (f"{level + 2} barang berharga RM{second} setiap satu. Berapakah jumlah harga?", f"RM{(level + 2) * second}", hint, explanation)
        if "bahagi" in topic:
            total = (level + 2) * second
            return (f"RM{total} dibahagi sama rata kepada {level + 2} murid. Berapakah seorang dapat?", f"RM{second}", hint, explanation)
        return (f"RM{first} ditambah RM{second}. Berapakah jumlahnya?", f"RM{first + second}", hint, explanation)

    if "tempoh" in topic:
        hours = 1 + level + (index % 2)
        minutes = 15 * (1 + (index % 3))
        if difficulty == "easy":
            return (
                f"Satu aktiviti berlangsung selama {hours} jam {minutes} minit. Berapakah tempoh itu dalam minit?",
                str((hours * 60) + minutes),
                "Tukar jam kepada minit, kemudian tambah baki minit.",
                explanation,
            )
        if difficulty == "medium":
            start_hour = 8 + (index % 3)
            duration_minutes = (hours * 60) + minutes
            end_hour = start_hour + (duration_minutes // 60)
            end_minute = duration_minutes % 60
            return (
                f"Aktiviti bermula pada pukul {start_hour}:00 pagi dan tamat pada pukul {end_hour}:{end_minute:02d} pagi. Berapakah tempoh dalam minit?",
                str(duration_minutes),
                "Cari beza masa tamat dan masa mula.",
                explanation,
            )
        second_hours = 1 + (index % 2)
        second_minutes = 20 + (index % 3) * 10
        total_minutes = (hours * 60) + minutes + (second_hours * 60) + second_minutes
        return (
            f"Dua aktiviti berlangsung selama {hours} jam {minutes} minit dan {second_hours} jam {second_minutes} minit. Berapakah jumlah tempoh dalam minit?",
            str(total_minutes),
            "Tukar kedua-dua tempoh kepada minit, kemudian tambah.",
            explanation,
        )
    if "masa" in topic or "waktu" in topic or "jam" in topic or "hari" in topic or "bulan" in topic or "tahun" in topic or "dekad" in topic or "abad" in topic:
        if "tolak" in topic:
            return (f"Tolak 1 jam {10 + index % 40} minit daripada {3 + level} jam 45 minit. Berapakah baki minit?", str(((3 + level) * 60 + 45) - (60 + 10 + index % 40)), hint, explanation)
        if "tambah" in topic:
            return (f"Tambah {level} jam {10 + index % 30} minit dengan 1 jam 20 minit. Berapakah jumlah dalam minit?", str((level * 60 + 10 + index % 30) + 80), hint, explanation)
        return build_time_conversion_question(difficulty, index, level, explanation)

    if "mililiter" in topic or "liter" in topic or "cecair" in topic:
        liters = 1 + level
        milliliters = 100 * (index % 5)
        return (
            f"{liters} L {milliliters} mL bersamaan berapa mL?",
            str((liters * 1000) + milliliters),
            "1 L = 1000 mL.",
            explanation,
        )
    if "gram" in topic or "kilogram" in topic or "jisim" in topic:
        kilograms = 1 + level
        grams = 50 * (index % 10)
        return (f"{kilograms} kg {grams} g bersamaan berapa g?", str((kilograms * 1000) + grams), "1 kg = 1000 g.", explanation)
    if "panjang" in topic or "sentimeter" in topic or "meter" in topic or "kilometer" in topic or "milimeter" in topic:
        meters = 2 + level
        centimeters = 10 * (index % 9)
        if "tolak" in topic:
            total = (meters * 100) + centimeters
            cut = 25 + (index % 4) * 10
            return (f"Sebuah tali {meters} m {centimeters} cm dipotong {cut} cm. Berapakah baki dalam cm?", str(total - cut), "Tukar meter kepada sentimeter sebelum menolak.", explanation)
        if "tambah" in topic:
            return (f"Tambah {meters} m {centimeters} cm dengan 1 m 20 cm. Berapakah jumlah dalam cm?", str((meters * 100 + centimeters) + 120), hint, explanation)
        return (f"{meters} m {centimeters} cm bersamaan berapa cm?", str((meters * 100) + centimeters), "1 m = 100 cm.", explanation)

    if "poligon" in topic:
        sides = [5, 6, 8, 10][index % 4]
        if difficulty == "easy":
            return (
                f"Sebuah poligon sekata mempunyai {sides} sisi sama panjang. Berapakah bilangan sisinya?",
                str(sides),
                "Poligon sekata mempunyai semua sisi yang sama panjang.",
                explanation,
            )
        if difficulty == "medium":
            side_length = 3 + level + (index % 4)
            return (
                f"Sebuah poligon sekata mempunyai {sides} sisi dan setiap sisi {side_length} cm. Berapakah perimeter?",
                str(sides * side_length),
                "Perimeter poligon sekata = bilangan sisi x panjang sisi.",
                explanation,
            )
        total_angle = (sides - 2) * 180
        return (
            f"Jumlah sudut pedalaman poligon {sides} sisi ialah berapa darjah?",
            str(total_angle),
            "Jumlah sudut pedalaman = (n - 2) x 180.",
            explanation,
        )
    if "sudut" in topic:
        sides = 4 + level
        total_angle = (sides - 2) * 180
        return (f"Jumlah sudut pedalaman poligon {sides} sisi ialah berapa darjah?", str(total_angle), "Jumlah sudut pedalaman = (n - 2) x 180.", explanation)
    if "perimeter" in topic:
        length = 5 + step
        width = 3 + level
        return (f"Sebuah segi empat tepat mempunyai panjang {length} cm dan lebar {width} cm. Berapakah perimeter?", str(2 * (length + width)), "Perimeter segi empat tepat = 2 x (panjang + lebar).", explanation)
    if "luas" in topic:
        length = 4 + step
        width = 2 + level
        return (f"Sebuah segi empat tepat mempunyai panjang {length} cm dan lebar {width} cm. Berapakah luasnya?", str(length * width), "Luas segi empat tepat = panjang x lebar.", explanation)
    if "isi padu" in topic:
        length = 2 + level
        width = 3 + (index % 3)
        height = 2 + (index % 2)
        return (f"Sebuah kuboid mempunyai panjang {length} cm, lebar {width} cm dan tinggi {height} cm. Berapakah isi padu?", str(length * width * height), "Isi padu kuboid = panjang x lebar x tinggi.", explanation)

    if "koordinat" in topic or "jarak" in topic:
        x1 = index % 5
        x2 = x1 + 3 + level
        return (f"Titik A berada pada ({x1}, 2) dan titik B pada ({x2}, 2). Berapakah jarak mengufuk AB?", str(x2 - x1), "Jarak mengufuk ialah beza nilai x.", explanation)
    if "nisbah" in topic:
        boys = 2 + level
        girls = boys * 2
        return (f"Nisbah murid lelaki kepada murid perempuan ialah {boys}:{girls}. Ringkaskan nisbah itu.", "1:2", "Bahagi kedua-dua kuantiti dengan faktor sepunya terbesar.", explanation)
    if "kadaran" in topic:
        unit_price = 3 + level
        quantity = 4 + (index % 4)
        return (f"Jika {quantity} buku berharga RM{unit_price * quantity}, berapakah harga 1 buku?", f"RM{unit_price}", "Bahagi jumlah harga dengan bilangan buku.", explanation)

    if "carta pai" in topic:
        percent = 25 + (index % 3) * 10
        total = 40
        return (f"Dalam carta pai, {percent}% daripada {total} murid memilih bola sepak. Berapakah bilangan murid itu?", str(total * percent // 100), "Cari peratus daripada jumlah murid.", explanation)
    if "mod" in topic or "julat" in topic or "median" in topic or "min" in topic:
        values = [4 + level, 6 + level, 6 + level, 8 + level, 10 + level]
        return (f"Data berikut ialah {', '.join(str(value) for value in values)}. Apakah mod?", str(6 + level), "Mod ialah nilai yang paling kerap muncul.", explanation)

    if "nombor bercampur" in topic or "peratus" in topic:
        numerator = 1 + (index % 3)
        denominator = 4
        percent = 100 + (numerator * 25)
        return (f"Tukar 1 {numerator}/{denominator} kepada peratus.", f"{percent}%", "Tukar nombor bercampur kepada pecahan atau perpuluhan dahulu.", explanation)
    if "darab pecahan" in topic:
        left = Fraction(1 + (index % 3), 4)
        right = Fraction(2 + (index % 2), 5)
        return (f"Darabkan pecahan berikut: {left} x {right} = ?", format_fraction(left * right), "Darab pengangka dengan pengangka dan penyebut dengan penyebut.", explanation)
    if "bundarkan perpuluhan" in topic:
        value = 2 + (index % 5) + Fraction(37 + index % 20, 100)
        return (f"Bundarkan {float(value):.2f} kepada nombor bulat terdekat.", str(round(float(value))), "Lihat digit persepuluh untuk membundar.", explanation)
    if "tambah dan tolak perpuluhan" in topic:
        first = 1.2 + (index % 5)
        second = 0.35 + (level * 0.1)
        return (f"Hitung {first:.2f} + {second:.2f}.", trim_decimal(first + second), "Susun titik perpuluhan sebelum menambah.", explanation)
    if "darab perpuluhan" in topic:
        first = 1.2 + (index % 4)
        multiplier = 2 + level
        return (f"Hitung {first:.1f} x {multiplier}.", trim_decimal(first * multiplier), "Darab seperti nombor bulat kemudian letakkan titik perpuluhan.", explanation)
    if "bahagi perpuluhan" in topic:
        divisor = 2 + level
        quotient = 1.5 + (index % 4)
        total = quotient * divisor
        return (f"Hitung {total:.1f} bahagi {divisor}.", trim_decimal(quotient), "Bahagi nombor perpuluhan dengan teliti.", explanation)
    if "pecahan" in topic:
        first = Fraction(1 + (index % 3), 4)
        second = Fraction(1 + ((index + 1) % 3), 6)
        return (f"Selesaikan pecahan berikut: {first} + {second} = ?", format_fraction(first + second), "Samakan penyebut sebelum menambah pecahan.", explanation)

    if "nombor perdana" in topic:
        number = [11, 13, 17, 19][index % 4]
        return (f"Adakah {number} nombor perdana? Jawab 1 untuk ya atau 0 untuk tidak.", "1", "Nombor perdana hanya mempunyai dua faktor.", explanation)
    if "pola" in topic:
        start = 2 + level
        pattern = [start, start + 3, start + 6]
        return (f"Pola nombor ialah {pattern[0]}, {pattern[1]}, {pattern[2]}, __. Apakah nombor seterusnya?", str(start + 9), "Cari beza antara nombor berturutan.", explanation)
    if "banding" in topic or "susun" in topic:
        numbers = [1000 + step, 1000 + step + 20, 1000 + step - 10]
        return (f"Susun nombor berikut menaik: {numbers[0]}, {numbers[1]}, {numbers[2]}. Apakah nombor pertama?", str(min(numbers)), "Menaik bermula daripada nombor paling kecil.", explanation)
    if "kenal" in topic or "tulis nombor" in topic:
        value = 30000 + (step * 100) + 25
        return (f"Apakah nilai digit ratus dalam nombor {value}?", str((value // 100) % 10 * 100), "Kenal pasti kedudukan digit ratus.", explanation)
    if "tolak" in topic:
        left = 100 + (step * 5)
        right = 20 + level
        return (f"Selesaikan: {left} - {right} = ?", str(left - right), hint, explanation)
    if "darab" in topic:
        left = 4 + level
        right = 3 + (index % 8)
        return (f"Selesaikan: {left} x {right} = ?", str(left * right), hint, explanation)
    if "bahagi" in topic:
        divisor = 2 + level
        answer = 4 + (index % 6)
        return (f"Selesaikan: {divisor * answer} bahagi {divisor} = ?", str(answer), hint, explanation)
    if "tambah" in topic:
        left = 100 + (step * 3)
        right = 20 + level
        return (f"Selesaikan: {left} + {right} = ?", str(left + right), hint, explanation)
    return (f"Selesaikan operasi Tahun 5 berikut: {10 + step} + {5 + level} = ?", str(15 + step + level), hint, explanation)


def build_time_conversion_question(difficulty: str, index: int, level: int, explanation: str) -> tuple[str, str, str, str]:
    if difficulty == "easy":
        days = 2 + (index % 5)
        hours = 2 + (index % 6)
        years = 1 + (index % 4)
        decades = 1 + (index % 3)
        centuries = 1 + (index % 2)
        variants = [
            (f"{days} hari bersamaan berapa jam?", str(days * 24), "1 hari = 24 jam."),
            (f"{hours} jam bersamaan berapa minit?", str(hours * 60), "1 jam = 60 minit."),
            (f"{years} tahun bersamaan berapa bulan?", str(years * 12), "1 tahun = 12 bulan."),
            (f"{decades} dekad bersamaan berapa tahun?", str(decades * 10), "1 dekad = 10 tahun."),
            (f"{centuries} abad bersamaan berapa tahun?", str(centuries * 100), "1 abad = 100 tahun."),
        ]
        prompt, answer, hint = variants[index % len(variants)]
        return prompt, answer, hint, explanation

    if difficulty == "medium":
        days = 2 + (index % 4)
        extra_hours = 3 + (index % 8)
        hours = 2 + (index % 5)
        minutes = [15, 20, 30, 45][index % 4]
        years = 1 + (index % 3)
        months = 2 + (index % 9)
        decades = 1 + (index % 4)
        extra_years = 2 + (index % 7)
        centuries = 1 + (index % 2)
        extra_decades = 1 + (index % 4)
        variants = [
            (
                f"{days} hari {extra_hours} jam bersamaan berapa jam?",
                str((days * 24) + extra_hours),
                "Tukar hari kepada jam, kemudian tambah baki jam.",
            ),
            (
                f"{hours} jam {minutes} minit bersamaan berapa minit?",
                str((hours * 60) + minutes),
                "Tukar jam kepada minit, kemudian tambah baki minit.",
            ),
            (
                f"{years} tahun {months} bulan bersamaan berapa bulan?",
                str((years * 12) + months),
                "Tukar tahun kepada bulan, kemudian tambah baki bulan.",
            ),
            (
                f"{decades} dekad {extra_years} tahun bersamaan berapa tahun?",
                str((decades * 10) + extra_years),
                "Tukar dekad kepada tahun, kemudian tambah baki tahun.",
            ),
            (
                f"{centuries} abad {extra_decades} dekad bersamaan berapa tahun?",
                str((centuries * 100) + (extra_decades * 10)),
                "Tukar abad dan dekad kepada tahun, kemudian tambah.",
            ),
            (
                f"{days} hari bersamaan berapa jam jika ditambah 1 hari {extra_hours} jam lagi?",
                str(((days + 1) * 24) + extra_hours),
                "Tukar semua hari kepada jam dahulu, kemudian tambah jam tambahan.",
            ),
        ]
        prompt, answer, hint = variants[index % len(variants)]
        return prompt, answer, hint, explanation

    days = 3 + (index % 5)
    extra_hours = 4 + (index % 7)
    subtract_hours = 1 + (index % 3)
    hours = 3 + (index % 6)
    minutes = [15, 25, 35, 45][index % 4]
    extra_minutes = [10, 20, 30, 40][index % 4]
    years = 2 + (index % 4)
    months = 3 + (index % 8)
    add_months = 4 + (index % 6)
    decades = 2 + (index % 4)
    extra_years = 5 + (index % 5)
    centuries = 1 + (index % 3)
    variants = [
        (
            f"Tempoh {days} hari {extra_hours} jam ditolak {subtract_hours} jam. Berapakah baki dalam jam?",
            str((days * 24) + extra_hours - subtract_hours),
            "Tukar hari kepada jam, kemudian tolak jam yang diberi.",
        ),
        (
            f"{hours} jam {minutes} minit ditambah {extra_minutes} minit. Berapakah jumlah dalam minit?",
            str((hours * 60) + minutes + extra_minutes),
            "Tukar jam kepada minit, kemudian tambah semua minit.",
        ),
        (
            f"{years} tahun {months} bulan ditambah {add_months} bulan. Berapakah jumlah dalam bulan?",
            str((years * 12) + months + add_months),
            "Tukar tahun kepada bulan sebelum menambah.",
        ),
        (
            f"{decades} dekad {extra_years} tahun ditolak {subtract_hours} tahun. Berapakah baki dalam tahun?",
            str((decades * 10) + extra_years - subtract_hours),
            "Tukar dekad kepada tahun, kemudian tolak.",
        ),
        (
            f"{centuries} abad {decades} dekad {extra_years} tahun bersamaan berapa tahun?",
            str((centuries * 100) + (decades * 10) + extra_years),
            "Tukar abad dan dekad kepada tahun, kemudian tambah baki tahun.",
        ),
        (
            f"Satu latihan mengambil {days} hari {extra_hours} jam, latihan kedua mengambil {subtract_hours} hari. Berapakah jumlah dalam jam?",
            str((days * 24) + extra_hours + (subtract_hours * 24)),
            "Tukar kedua-dua tempoh kepada jam, kemudian tambah.",
        ),
    ]
    prompt, answer, hint = variants[index % len(variants)]
    return prompt, answer, hint, explanation


def difficulty_level(difficulty: str) -> int:
    return {"easy": 1, "medium": 2, "hard": 3}.get(difficulty, 2)


def trim_decimal(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def build_options(answer: str, index: int) -> list[str]:
    if answer.lower().startswith("rm"):
        value = Fraction(answer.lower().removeprefix("rm"))
        delta = 2 + (index % 5)
        return unique_options([answer, format_money(value + delta), format_money(max(Fraction(0), value - delta)), format_money(value + (2 * delta))])
    if answer.endswith("%"):
        value = int(answer.removesuffix("%"))
        return unique_options([answer, f"{value + 5}%", f"{max(0, value - 5)}%", f"{value + 10}%"])
    if ":" in answer:
        # 处理比例格式 (e.g., "1:2")
        parts = [int(part) for part in answer.split(":", maxsplit=1)]
        a, b = parts[0], parts[1]
        return unique_options(
            [
                answer,
                f"{a + 1}:{b}",
                f"{a}:{b + 1}",
                f"{a + 1}:{b + 1}",
            ]
        )
    if "/" in answer:
        numerator, denominator = [int(part) for part in answer.split("/", maxsplit=1)]
        return unique_options(
            [
                answer,
                f"{numerator + index}/{denominator}",
                f"{max(1, numerator - index)}/{denominator}",
                f"{denominator}/{max(1, numerator)}",
            ]
        )
    value = Fraction(answer)
    delta = 1 + (index % 5)
    return unique_options(
        [
            answer,
            format_number(value + delta),
            format_number(max(Fraction(0), value - delta)),
            format_number(value + (2 * delta)),
        ]
    )


def normalize_generated_options(question_type: str, answer: str, options: list[str]) -> list[str]:
    if question_type != "multiple_choice":
        return []
    fallback_options = []
    try:
        fallback_options = build_options(answer, 1)
    except Exception:
        fallback_options = []
    return unique_options([answer, *[str(option) for option in options], *fallback_options])[:4]


def unique_options(options: list[str]) -> list[str]:
    unique = []
    for option in options:
        if option not in unique:
            unique.append(option)
    return unique


def format_number(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return trim_decimal(float(value))


def format_money(value: Fraction) -> str:
    if value.denominator == 1:
        return f"RM{value.numerator}"
    return f"RM{float(value):.2f}"
