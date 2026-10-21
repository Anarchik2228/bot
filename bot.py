import discord
from discord.ui import Button, View, Modal, TextInput
from discord.ext import commands
import re
import os
import traceback

# ================= НАСТРОЙКИ =================
# Токен (лучше использовать переменную окружения, но можно вписать сюда)
DISCORD_TOKEN = ("MTU2MjA1NDkxNTkwNjQ3NDA1NA.GIbDaN.C211x_zD3Z7dhKswwVMEwG41UTwn4XybUD_66I")

# ID текстового канала, КУДА бот будет отправлять панель (не категории!)
ID_CHANNEL_BUTTON = 1534887904852312164 # <--- ОБЯЗАТЕЛЬНО ВПИШИТЕ ID КАНАЛА

ID_CHANNEL_MODERATION = 1534887905309233166
ID_CHANNEL_LOGS = 1534887905309233168
ID_CATEGORY_CHATS = 1562093227710881792

# ID роли рекрутера (кто может нажимать кнопки). None = проверка отключена.
ID_RECRUITER_ROLE = None

STATE_FILE = "bot_state.txt"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


# ================= УТИЛИТЫ =================

def load_button_message_id():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None

def save_button_message_id(msg_id: int):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(str(msg_id))

def is_recruiter(member: discord.Member) -> bool:
    if ID_RECRUITER_ROLE is None:
        return True
    return any(role.id == ID_RECRUITER_ROLE for role in getattr(member, "roles", []))


# ================= ПАНЕЛЬ =================

class ApplyButtonView(View):
    def __init__(self, bot_instance):
        super().__init__(timeout=None)
        self.bot = bot_instance

    @discord.ui.button(
        label="Подать заявку",
        style=discord.ButtonStyle.blurple,
        emoji="📝",
        custom_id="onyx_apply_button",
    )
    async def apply_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(ApplicationModal(self.bot))


# ================= МОДАЛЬНЫЕ ОКНА =================

class ApplicationModal(Modal, title="Заявка на вступление в Onyx"):
    def __init__(self, bot_instance):
        super().__init__()
        self.bot = bot_instance

    irl_info = TextInput(label="IRL Имя / Возраст | Ник / Статик", placeholder="Иван / 18 / Rick / 228", required=True)
    rp_experience = TextInput(label="Опыт на RP проектах", placeholder="Опишите опыт", required=True)
    lvl_online = TextInput(label="Lvl в игре / Средний онлайн", placeholder="2 / 2-3ч", required=True)
    rollback_special = TextInput(label="Откаты спеш/сайга", style=discord.TextStyle.long, placeholder="Ссылки на откаты или описание", required=True)
    rollback_mp = TextInput(label="Откаты с МП (B33, MCL, Capt)", placeholder="Ссылки на откаты или описание", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🆕 НОВАЯ ЗАЯВКА В СЕМЬЮ ONYX", color=discord.Color.blue())
        
        embed.add_field(name="👤 Заявитель", value=f"{interaction.user.mention} (ID: {interaction.user.id})", inline=False)
        embed.add_field(name="📝 IRL / Игровой ник", value=f"`{self.irl_info.value}`", inline=False)
        embed.add_field(name="🎮 Опыт на RP проектах", value=f"`{self.rp_experience.value}`", inline=False)
        embed.add_field(name="📊 Lvl / Средний онлайн", value=f"`{self.lvl_online.value}`", inline=False)
        embed.add_field(name="🎬 Откаты спеш/сайга", value=f"`{self.rollback_special.value}`", inline=False)
        embed.add_field(name="🎮 Откаты с МП", value=f"`{self.rollback_mp.value}`", inline=False)
        embed.set_footer(text=f"Время подачи: {interaction.created_at}")

        mod_channel = self.bot.get_channel(ID_CHANNEL_MODERATION)
        if isinstance(mod_channel, discord.TextChannel):
            action_view = RecruiterActionsView(self.bot, interaction.user, embed)
            msg = await mod_channel.send(embed=embed, view=action_view)
            action_view.message_id = msg.id
            action_view.channel_id = mod_channel.id
        else:
            print("❌ Канал модерации не найден или не является текстовым каналом!")

        await interaction.response.send_message("✅ Твоя заявка отправлена рекрутерам семьи Onyx!", ephemeral=True)


class DenyModal(Modal, title="Причина отказа"):
    def __init__(self, bot_instance, applicant_user, original_embed, message_ref):
        super().__init__()
        self.bot = bot_instance
        self.applicant = applicant_user
        self.original_embed = original_embed
        self.message_ref = message_ref

    reason = TextInput(
        label="Укажите причину отказа",
        style=discord.TextStyle.long,
        placeholder="Например: низкий онлайн, отсутствие опыта...",
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        updated_embed = self.original_embed.copy()
        updated_embed.color = discord.Color.red()
        updated_embed.title = "🆕 ЗАЯВКА: ОТКАЗАНА"
        updated_embed.add_field(name="❌ Причина отказа", value=f"`{self.reason.value}`", inline=False)

        if self.message_ref:
            try:
                await self.message_ref.edit(embed=updated_embed, view=None)
            except Exception as e:
                print(f"Ошибка редактирования заявки: {e}")

        log_channel = self.bot.get_channel(ID_CHANNEL_LOGS)
        if isinstance(log_channel, discord.TextChannel):
            await log_channel.send(
                f"❌ **ОТКАЗ В ЗАЯВКЕ**\n"
                f"Игрок: {self.applicant.mention}\n"
                f"Рекрутер: {interaction.user.mention}\n"
                f"Причина: `{self.reason.value}`"
            )

        try:
            dm = await self.applicant.create_dm()
            await dm.send(
                f"😕 К сожалению, твоя заявка отклонена.\n"
                f"📜 Причина: `{self.reason.value}`\n"
                f"Обратись к Главному Рекрутеру, если считаешь это ошибкой."
            )
        except discord.Forbidden:
            print(f"Не удалось отправить ЛС пользователю {self.applicant.name}.")

        await interaction.response.send_message("✅ Заявка отклонена. Игроку отправлено ЛС.", ephemeral=True)


# ================= ДЕЙСТВИЯ РЕКРУТЕРА =================

class RecruiterActionsView(View):
    def __init__(self, bot_instance, applicant_user, original_embed):
        super().__init__(timeout=None)
        self.bot = bot_instance
        self.applicant = applicant_user
        self.original_embed = original_embed
        self.message_id = None
        self.channel_id = None
        self.chat_channel_id = None

    def _get_message(self):
        if self.channel_id and self.message_id:
            channel = self.bot.get_channel(self.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    return channel.get_partial_message(self.message_id)
                except Exception:
                    return None
        return None

    async def _deny_if_not_recruiter(self, interaction: discord.Interaction) -> bool:
        if not is_recruiter(interaction.user):
            await interaction.response.send_message("❌ У вас нет прав рекрутера.", ephemeral=True)
            return True
        return False

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.green, row=0, custom_id="onyx_accept")
    async def accept_callback(self, interaction: discord.Interaction, button: Button):
        if await self._deny_if_not_recruiter(interaction):
            return
        await self.process_decision(interaction, "ПРИНЯТА", discord.Color.green())

    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.red, row=0, custom_id="onyx_deny")
    async def deny_callback(self, interaction: discord.Interaction, button: Button):
        if await self._deny_if_not_recruiter(interaction):
            return
        msg = interaction.message or self._get_message()
        await interaction.response.send_modal(DenyModal(self.bot, self.applicant, self.original_embed, msg))

    @discord.ui.button(label="📞 Вызвать на обзвон", style=discord.ButtonStyle.blurple, row=0, custom_id="onyx_call")
    async def call_callback(self, interaction: discord.Interaction, button: Button):
        if await self._deny_if_not_recruiter(interaction):
            return
        await interaction.response.send_message(f"✅ Вызвали {self.applicant.mention} на обзвон!", ephemeral=True)

        log_channel = self.bot.get_channel(ID_CHANNEL_LOGS)
        if isinstance(log_channel, discord.TextChannel):
            await log_channel.send(
                f"🔔 **ОБЗВОН:** {self.applicant.mention} вызван рекрутером {interaction.user.mention}."
            )

        updated_embed = self.original_embed.copy()
        updated_embed.color = discord.Color.gold()
        updated_embed.title = "🆕 ЗАЯВКА: НА ОБЗВОНЕ"
        updated_embed.add_field(name="👤 Взял на обзвон", value=f"{interaction.user.mention} ({interaction.user.name})", inline=False)
        updated_embed.add_field(name="🟡 СТАТУС", value="Ожидает обзвона", inline=False)
        self.original_embed = updated_embed

        msg = interaction.message or self._get_message()
        if msg:
            try:
                await msg.edit(embed=updated_embed, view=self)
            except Exception as e:
                print(f"Ошибка обновления заявки: {e}")

    @discord.ui.button(label="💬 Открыть чат", style=discord.ButtonStyle.grey, row=1, custom_id="onyx_chat")
    async def chat_callback(self, interaction: discord.Interaction, button: Button):
        if await self._deny_if_not_recruiter(interaction):
            return

        category = self.bot.get_channel(ID_CATEGORY_CHATS)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("❌ Категория для чатов не найдена!", ephemeral=True)
            return

        raw_name = self.applicant.display_name
        channel_name = raw_name[:50]
        channel_name = "".join(c if c.isalnum() or c in "-_" else "-" for c in channel_name)
        if not channel_name:
            channel_name = f"chat-{self.applicant.id}"

        try:
            new_channel = await category.create_text_channel(name=channel_name, reason=f"Чат для {self.applicant.name}")
            await new_channel.set_permissions(
                self.applicant,
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                add_reactions=True,
            )
            self.chat_channel_id = new_channel.id

            mod_channel = self.bot.get_channel(ID_CHANNEL_MODERATION)
            if isinstance(mod_channel, discord.TextChannel):
                await mod_channel.send(f"🗣️ **Чат создан!** Кандидат: {self.applicant.mention}, Канал: {new_channel.mention}")

            try:
                dm = await self.applicant.create_dm()
                await dm.send(f"🗣️ Чат с рекрутерами создан! Перейди по ссылке: {new_channel.mention}")
            except discord.Forbidden:
                pass

            updated_embed = self.original_embed.copy()
            updated_embed.fields = [f for f in updated_embed.fields if f.name != "🗣️ Чат с рекрутерами"]
            updated_embed.add_field(name="🗣️ Чат с рекрутерами", value=f"<#{new_channel.id}>", inline=False)
            self.original_embed = updated_embed

            msg = interaction.message or self._get_message()
            if msg:
                try:
                    await msg.edit(embed=updated_embed, view=self)
                except Exception as e:
                    print(f"Ошибка обновления заявки: {e}")

            await interaction.response.send_message(f"✅ Чат создан: {new_channel.mention}", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ У бота нет прав на создание каналов!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Ошибка: {e}", ephemeral=True)
            print(f"Ошибка создания: {e}")
            traceback.print_exc()

    @discord.ui.button(label="🗑️ Удалить чат", style=discord.ButtonStyle.red, row=1, custom_id="onyx_delete_chat")
    async def delete_chat_callback(self, interaction: discord.Interaction, button: Button):
        if await self._deny_if_not_recruiter(interaction):
            return

        channel_id = self.chat_channel_id
        if not channel_id:
            for field in self.original_embed.fields:
                if field.name == "🗣️ Чат с рекрутерами":
                    match = re.search(r"<#(\d+)>", field.value)
                    if match:
                        channel_id = int(match.group(1))
                    break

        if not channel_id:
            await interaction.response.send_message("❌ Чат для этой заявки ещё не создавался!", ephemeral=True)
            return

        target_channel = self.bot.get_channel(channel_id)
        if isinstance(target_channel, discord.TextChannel):
            try:
                await target_channel.delete(reason=f"Удаление чата рекрутинга по инициативе {interaction.user.name}")

                log_channel = self.bot.get_channel(ID_CHANNEL_LOGS)
                if isinstance(log_channel, discord.TextChannel):
                    await log_channel.send(
                        f"🗑️ **ЧАТ УДАЛЁН**\n"
                        f"Кандидат: {self.applicant.mention}\n"
                        f"Инициатор: {interaction.user.mention}"
                    )

                updated_embed = self.original_embed.copy()
                updated_embed.fields = [f for f in updated_embed.fields if f.name != "🗣️ Чат с рекрутерами"]
                updated_embed.add_field(name="🗣️ Чат с рекрутерами", value="❌ Чат удалён", inline=False)
                self.original_embed = updated_embed
                self.chat_channel_id = None

                msg = interaction.message or self._get_message()
                if msg:
                    try:
                        await msg.edit(embed=updated_embed, view=self)
                    except Exception as e:
                        print(f"Ошибка при обновлении заявки: {e}")

                await interaction.response.send_message("✅ Чат успешно удалён. Заявка обновлена.", ephemeral=True)

            except discord.Forbidden:
                await interaction.response.send_message("❌ У бота нет прав на удаление этого канала!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Не удалось удалить чат: {e}", ephemeral=True)
                print(f"Ошибка удаления: {e}")
                traceback.print_exc()
        else:
            self.chat_channel_id = None
            updated_embed = self.original_embed.copy()
            updated_embed.fields = [f for f in updated_embed.fields if f.name != "🗣️ Чат с рекрутерами"]
            updated_embed.add_field(name="🗣️ Чат с рекрутерами", value="❌ Канал не найден", inline=False)
            self.original_embed = updated_embed

            msg = interaction.message or self._get_message()
            if msg:
                try:
                    await msg.edit(embed=updated_embed, view=self)
                except Exception as e:
                    print(f"Ошибка обновления: {e}")

            await interaction.response.send_message("⚠️ Канал не найден. Заявка обновлена.", ephemeral=True)

    async def process_decision(self, interaction: discord.Interaction, status: str, color: discord.Color):
        updated_embed = self.original_embed.copy()
        updated_embed.color = color
        updated_embed.title = f"🆕 ЗАЯВКА: {status}"
        updated_embed.add_field(
            name="✅ Решение",
            value=f"Принял: {interaction.user.mention} ({interaction.user.name})",
            inline=False,
        )
        self.original_embed = updated_embed

        msg = interaction.message or self._get_message()
        if msg:
            try:
                await msg.edit(embed=updated_embed, view=None)
            except Exception as e:
                print(f"Ошибка обновления заявки: {e}")

        log_channel = self.bot.get_channel(ID_CHANNEL_LOGS)
        if isinstance(log_channel, discord.TextChannel):
            await log_channel.send(
                f"✅ **ЗАЯВКА {status}**\n"
                f"Игрок: {self.applicant.mention}\n"
                f"Рекрутер: {interaction.user.mention}"
            )

        try:
            dm = await self.applicant.create_dm()
            await dm.send(
                f"🎉 Поздравляем! Твоя заявка в семью **Onyx** {status.lower()}!\n"
                f"Свяжись с рекрутерами для дальнейших шагов."
            )
        except discord.Forbidden:
            print(f"Не удалось отправить ЛС пользователю {self.applicant.name}.")

        await interaction.response.send_message(f"✅ Заявка {status.lower()}. Игроку отправлено ЛС.", ephemeral=True)


# ================= ПУБЛИКАЦИЯ ПАНЕЛИ =================

async def publish_panel():
    print("⏳ Начинаю публикацию панели...")
    channel = bot.get_channel(ID_CHANNEL_BUTTON)
    
    if not channel:
        print(f"❌ Канал не найден! Убедитесь, что ID_CHANNEL_BUTTON = {ID_CHANNEL_BUTTON} — это правильный ID ТЕКСТОВОГО канала.")
        return
        
    if not isinstance(channel, discord.TextChannel):
        print(f"❌ ID_CHANNEL_BUTTON = {ID_CHANNEL_BUTTON} указывает на {type(channel).__name__}, а нужен текстовый канал (TextChannel)!")
        return

    # Текст приветствия
    welcome_text = (
        "Добро пожаловать в **Onyx**!\n\n"
        "Перед подачей заявки внимательно ознакомься с правилами и требованиями семьи.\n\n"
        "• Активный онлайн (указывай реальное время)\n"
        "• Наличие отката с арены/МП (видео обязательно)\n"
        "• Адекватность и командная игра\n"
        "• Возраст 15+ (указывай в заявке, бывают исключения)\n\n"
        "Нажми на кнопку «Подать заявку» ниже и заполни все поля максимально подробно.\n\n"
        "После отправки заявку рассмотрят рекрутеры и руководство. О результате тебе придет уведомление в ЛС.\n\n"
        "Удачи! 🍀"
    )

    # 1. Пробуем отредактировать старое сообщение (если оно есть)
    existing_id = load_button_message_id()
    if existing_id:
        try:
            msg = await channel.fetch_message(existing_id)
            
            embed = discord.Embed(
                title="📝 Заявка в семью Onyx",
                description=welcome_text,  # <--- Вставляем текст сюда
                color=discord.Color.blurple(),
            )
            
            image_path = "onyx_logo.png"
            if os.path.exists(image_path):
                file = discord.File(image_path, filename="onyx_logo.png")
                embed.set_image(url="attachment://onyx_logo.png")
                await msg.edit(embed=embed, view=ApplyButtonView(bot), attachments=[file])
            else:
                print("⚠️ Файл onyx_logo.png не найден, обновляем без картинки.")
                await msg.edit(embed=embed, view=ApplyButtonView(bot))
                
            print(f"♻️ Старая панель успешно обновлена (msg_id={existing_id})")
            return
        except discord.NotFound:
            print("⚠️ Старое сообщение удалено из Discord, создаём новое.")
        except Exception as e:
            print(f"⚠️ Ошибка при обновлении старого сообщения: {e}")

    # 2. Создаём новое сообщение, если старого нет
    print("⏳ Создаю новое сообщение с кнопкой...")
    embed = discord.Embed(
        title="📝 Заявка в семью Onyx",
        description=welcome_text,  # <--- Вставляем текст сюда
        color=discord.Color.blurple(),
    )
    
    image_path = "onyx_logo.png"
    if os.path.exists(image_path):
        print("🖼️ Файл картинки найден, прикрепляю...")
        file = discord.File(image_path, filename="onyx_logo.png")
        embed.set_image(url="attachment://onyx_logo.png")
        msg = await channel.send(embed=embed, view=ApplyButtonView(bot), file=file)
    else:
        print("⚠️ Файл onyx_logo.png не найден в папке с ботом! Отправляем без картинки.")
        msg = await channel.send(embed=embed, view=ApplyButtonView(bot))

    save_button_message_id(msg.id)
    print(f"✅ Панель опубликована (msg_id={msg.id})")


# ================= СОБЫТИЯ =================

@bot.event
async def on_ready():
    print(f"🤖 Бот запущен как {bot.user} (ID: {bot.user.id})")

    # Выводим в консоль информацию о канале для проверки
    ch = bot.get_channel(ID_CHANNEL_BUTTON)
    if ch:
        print(f"📍 ID_CHANNEL_BUTTON указывает на: {type(ch).__name__} | Название: '{ch.name}'")
    else:
        print(f"❌ ID_CHANNEL_BUTTON={ID_CHANNEL_BUTTON} не найден на сервере!")

    bot.add_view(ApplyButtonView(bot))
    try:
        await bot.tree.sync()
        print("✅ Slash-команды синхронизированы.")
    except Exception as e:
        print(f"⚠️ Ошибка синхронизации команд: {e}")

    try:
        await publish_panel()
    except Exception as e:
        print(f"❌ Критическая ошибка при публикации панели: {e}")
        traceback.print_exc()


@bot.tree.command(name="panel", description="Опубликовать панель с кнопкой подачи заявки")
@discord.app_commands.default_permissions(administrator=True)
async def panel_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await publish_panel()
    await interaction.followup.send("✅ Команда выполнена. Проверьте консоль бота.", ephemeral=True)


if __name__ == "__main__":
    if not DISCORD_TOKEN or DISCORD_TOKEN.startswith("ВСТАВЬТЕ"):
        raise SystemExit("❌ Не задан DISCORD_TOKEN. Установите переменную окружения DISCORD_TOKEN.")
    bot.run(DISCORD_TOKEN)
