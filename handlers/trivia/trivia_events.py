import random
from pyrogram import Client, types
from config import ENABLE_TRIVIA_EVENTS

async def message_event(client: Client, message: types.Message):
    # Check if trivia events are enabled
    if not ENABLE_TRIVIA_EVENTS:
        return

    # Ensure the message and its text exist
    if not message or not message.text:
        return

    text = message.text

    # تثبيحات
    if text.startswith("ثبح ") or text == "ثبح":
        await message.reply("ثباحو")
    elif text.startswith("ثباحو ") or text == "ثباحو":
        await message.reply("ثبح")
    elif text.startswith("مثائو ") or text == "مثائو":
        await message.reply("مثا")
    elif text.startswith("مثا ") or text == "مثا":
        await message.reply("مثائو")

    # يالبوت
    if "يالبوت" in text and text.count("يالبوت") > text.count("يالبوتة"):
        normal_responses = [
            "اكيد يسطا", "اكيد يبرو", "بدون شك", "يب اكيد", "طبعا", "اومال", "ايوه",
            "يب", "يب يب", "اتكل علي الله يعم", "مش فايقلك",
            "هي دي محتاجه سؤال!؟", "لا", "انا بقولك لا", "اكيد لا", "نوب", "معرفش",
            "اكيد يغالي", "اكيد ينقم", "لا هه", "صدقني انا ذات نفسي معرفش", "انا لو أعرف هقولك"
        ]
        hellos = ["نعم", "نعم يغالي", "نعم ينقم", "عايز ايه", "نعم يخويا"]
        steins_keys = ["stein", "شتاين", "ستاين"]
        steins = [
            "شتاينز الأعظم", "شتاينز فوق", "شتاينز فوق مستوي التقييم البشري", "شتاينز اعظم انمي"
        ]
        shinobi_keywords = ["shinobi", "شنوبي", "شنبي", "شنوب", "شينوبي"]
        father = [
            "شنوبي ابويا وعمي وعم عيالي", "شنبي ابويا وعمي", "شنوبي احسن اب في العالم"
        ]
        azab = [
            "ده حنين عليا خالث", "بابا شنبي مش بيمد ايده عليا", "مش بيلمسني"
        ]
        tabla = [
            "لا طبعا يغالي", "شنوبي عمي وعم عيالي", "شنوبي عمك", "شنوبي فوق"
        ]
        love = ["حبك", "حبق", "وانا كمان يغالي", "+1"]
        win = ["مش هتكسب هه", "نصيبك مش هتكسب", "انا بقولك لا", "على ضمانتي"]
        elhal = ["الحمدلله يخويا", "الحمدلله يغالي", "تمام الحمدلله"]

        # me responses
        if "انا" in text:
            sender = message.from_user
            if sender and sender.username == "Shinobi7k":
                if "ابوك" in text:
                    await message.reply(random.choice(father))
                    return

        # shinobi responses
        for word in shinobi_keywords:
            if word in text:
                if "ابوك" in text:
                    await message.reply(random.choice(father))
                    return
                if "بيعذبك" in text:
                    await message.reply(random.choice(azab))
                    return
                if "بتطبل" in text:
                    await message.reply(random.choice(tabla))
                    return

        # steins responses
        for word in steins_keys:
            if word in text:
                await message.reply(random.choice(steins))
                return

        # exceptions
        if "هكسب" in text:
            await message.reply(random.choice(win))
            return
        if "حبك" in text or "حبق" in text:
            await message.reply(random.choice(love))
            return
        if "عامل ايه" in text or "عامل إيه" in text or "كيف حالك" in text:
            await message.reply(random.choice(elhal))
            return

        # normal responses
        if " " in text:
            await message.reply(random.choice(normal_responses))
        else:
            await message.reply(random.choice(hellos))
