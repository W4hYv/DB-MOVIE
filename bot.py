import discord
from discord.ext import commands, tasks
from logic import DatabaseManager, hide_img, create_collage
from config import TOKEN, DATABASE
import os
import cv2

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

manager = DatabaseManager(DATABASE)
manager.create_tables()

@bot.command()
async def start(ctx):
    user_id = ctx.author.id
    if user_id in manager.get_users():
        await ctx.send("Kamu sudah terdaftar!")
    else:
        manager.add_user(user_id, ctx.author.name)
        await ctx.send("Hai! Selamat datang! Kamu telah berhasil terdaftar! Kamu akan menerima gambar baru secara berkala, dan kamu memiliki kesempatan untuk mendapatkannya dengan mengklik tombol 'Ambil!'")

@tasks.loop(minutes=1)
async def send_message():
    users = manager.get_users()
    if not users:
        return
    
    try:
        prize_data = manager.get_random_prize()
    except IndexError:
        return 

    prize_id, img = prize_data[0], prize_data[1]
    hide_img(img)

    for user_id in users:
        try:
            user = await bot.fetch_user(user_id) 
            if user:
                await send_image(user, f'hidden_img/{img}', prize_id)
        except Exception as e:
            print(f"Gagal mengirim pesan ke user {user_id}: {e}")
            
    manager.mark_prize_used(prize_id)

async def send_image(user, image_path, prize_id):
    if os.path.exists(image_path):
        with open(image_path, 'rb') as img:
            file = discord.File(img)
            button = discord.ui.Button(label="Ambil!", custom_id=str(prize_id))
            view = discord.ui.View()
            view.add_item(button)
            await user.send(file=file, view=view)

@bot.command()
async def rating(ctx):
    res = manager.get_rating()
    if not res:
        await ctx.send("Belum ada pemenang sama sekali.")
        return
    
    formatted_res = [f'| @{x[0]:<11} | {x[1]:<11}|\n{"_"*26}' for x in res]
    formatted_res = '\n'.join(formatted_res)
    final_res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + formatted_res
    await ctx.send(f"```\n{final_res}\n```")

@bot.command(name="score")
async def get_my_score(ctx):
    user_id = ctx.author.id

    info = manager.get_winners_img(user_id)
    prizes = [x[0] for x in info]

    if not os.path.exists('img'):
        await ctx.send("Folder 'img' tidak ditemukan.")
        return
        
    image_paths = os.listdir('img')
    image_paths = [f'img/{x}' if x in prizes else f'hidden_img/{x}' for x in image_paths]

    collage = create_collage(image_paths)
    
    if collage is not None:
        collage_path = f'collage_{user_id}.png'
        cv2.imwrite(collage_path, collage)
        
        with open(collage_path, 'rb') as f:
            file = discord.File(f)
            await ctx.send(content="Nih kolase pencapaian gambar kamu! Yang udah dibuka berarti menang, yang masih pixelated berarti belum didapat.", file=file)

        if os.path.exists(collage_path):
            os.remove(collage_path)
    else:
        await ctx.send("Gagal membuat kolase karena gambar tidak tersedia.")

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.component:
        custom_id = int(interaction.data['custom_id'])
        user_id = interaction.user.id

        if manager.get_winners_count(custom_id) < 3:
            res = manager.add_winner(user_id, custom_id)
            if res:
                img = manager.get_prize_img(custom_id)
                img_path = f'img/{img}'
                if os.path.exists(img_path):
                    with open(img_path, 'rb') as photo:
                        file = discord.File(photo)
                        await interaction.response.send_message(file=file, content="Selamat, kamu mendapatkan gambar!")
                else:
                    await interaction.response.send_message(content="Gambar asli tidak ditemukan di server.", ephemeral=True)
            else:
                await interaction.response.send_message(content="Kamu sudah mendapatkan gambar ini sebelumnya!", ephemeral=True)
        else:
            await interaction.response.send_message(content="Maaf, sudah 3 orang tercepat yang mendapatkan gambar ini.", ephemeral=True)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    if not send_message.is_running():
        send_message.start()

bot.run(TOKEN)
