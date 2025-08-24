# sakinah-moments-daily## To run the project, follow these steps:

# install an older Python alongside 3.13
brew install python@3.12

# make a 3.12 virtualenv
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv312
source .venv312/bin/activate
python -m pip install --upgrade pip
pip install Flask==3.0.2 Pillow==10.2.0

python3 main.py


## To build the docker image:
docker build -t sakinah:latest .

## To run the container based on the image:
docker run --rm -p 5123:5123 sakinah:latest

## To Test the curl:
# Local
curl --location 'http://192.168.1.180:5123/generate' \
--form 'text="اللهم إني أعوذ بك من العجز والكسل، والجبن والبخل،  والهرم وعذاب القبر، اللهم آت نفسي تقواها، وزكها أنت خير من زكاها، أنت وليها ومولاها اللهم إني أعوذ بك من علم لا ينفع ومن قلب لا يخشع، ومن نفس لا تشبع، ومن دعوة لا يستجاب لها."'

# Hosted
curl --location 'https://sakinah.omaralashi.space/generate' \
--form 'text="اللهم إني أعوذ بك من العجز والكسل، والجبن والبخل،  والهرم وعذاب القبر، اللهم آت نفسي تقواها، وزكها أنت خير من زكاها، أنت وليها ومولاها اللهم إني أعوذ بك من علم لا ينفع ومن قلب لا يخشع، ومن نفس لا تشبع، ومن دعوة لا يستجاب لها."'