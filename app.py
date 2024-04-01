from flask import Flask, render_template, request, redirect, make_response
import requests
import discordoauth2
from time import sleep
from bs4 import BeautifulSoup

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

MVO = discordoauth2.Client(clientid, secret=clientsecret, redirect=redirect_ur if app.debug == False else "http://localhost:5000/mvo/ident", bot_token=token)

MVO.update_linked_roles_metadata([])

worlds = requests.get("https://xivapi.com/servers/dc").json()

session = requets.Session()

def obf(code):
	return code.swapcase()  # Author's Note: You do not want to give users access to their Access Key otherwise they can submit any data
							# I would not recommend using .swapcase() since while it's idiot proof, someone's going to eventually find out

def deobf(code):
	return obf(code)

@app.route('/mvo/')
def mvoredirect():
	return redirect(MVO.generate_uri(scope=["identify", "role_connections.write"], skip_prompt=True))

@app.route("/mvo/search", methods=['POST'])
def searchcharacter():
	name = request.form.get("name").replace(" ", "+")
	world = request.form.get("world")

	if world == None or name == None:
		return []
	if not session.post("https://www.google.com/recaptcha/api/siteverify", params={"secret":captchakey, "response": request.form.get('gc')}).json()["success"]:
		return []

	r = session.get(f"https://eu.finalfantasyxiv.com/lodestone/character/?q={name.lower()}&worldname={world}")
	if not r.ok:
		return []
	page = BeautifulSoup(r.content, "html.parser")
	res = []
	for i in page.select("div.entry > a.entry__link"):
		res.append(( i.p.text, i['href'].split('/')[-2], i.find('img')['src']))
	return res


def fetchcharacter(id):
	r = session.get(f"https://eu.finalfantasyxiv.com/lodestone/character/{id}/")
	if not r.ok:
		return "err"
	page = BeautifulSoup(r.content, "html.parser")
	
	info = page.select_one("div.character-block .character-block__name").text
	profile = page.select_one("div.character__selfintroduction").text
	name = page.select_one("p.frame__chara__name").text
	if "Viera" in info and info[-1] == "♂":
		return [True, profile, name]
	return [False, profile]


@app.route("/mvo/ident")
def callback():
	code = request.args.get("code")
	if code != None:
		try:
			access = MVO.exchange_code(code=code)
		except discordoauth2.exceptions.HTTPException as e:
			print(e)
			return redirect(MVO.generate_uri(scope=["identify", "role_connections.write"], skip_prompt=True))
		userid = access.fetch_identify()
		print("user login", userid['username'])

		
		return render_template("ident.html", code=obf(access.token), user=userid, worlds=worlds)
	else:
		return redirect(MVO.generate_uri(scope=["identify", "role_connections.write"], skip_prompt=True))


@app.route("/mvo/link", methods=['POST'])
def link():
	code = request.form.get("code")
	cid = request.form.get("character")

	if not requests.post("https://www.google.com/recaptcha/api/siteverify", params={"secret":captchakey, "response": request.form.get('gc')}).json()["success"]:
		return {"err": "Failed Captcha"}

	if code == None or cid == None:
		return {"err": "No Data"}

	access = MVO.from_access_token(deobf(code))
	user = access.fetch_identify()
	
	try:
		character = fetchcharacter(cid)
	except:
		return ({"err": "Server Error"})
	if not character[0]:
		return ({"err": "not bunny bunny"})
	if not user["id"] in character[1]:
		return ({"err" :f"Auth ID not found on profile\n\nLodestone Returned:\n{character[1]}\n\nExpected (eg.):\n" + (f"{character[1]}\n{user['id']}" if character[1] != "-" else user['id'])})

	for attempt in range(5):
		try:
			access.update_metadata("Bunny", character[2])
			return ({"msg": "Link Successful. You can close this page."})
		except discordoauth2.exceptions.RateLimited as e:
			print("rate limited, retry in", e.retry_after)
			sleep(e.retry_after)
		except discordoauth2.exceptions.HTTPException as e:
			return message({"err": "Discord rejected our request"})
	return message("<h1>A bug has occured")