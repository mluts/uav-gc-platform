.PHONY: run uav-sitl rm-uav-sitl check repl

run: uav-sitl
	docker run -it --rm -p 127.0.0.1:5762:5762 uav-sitl

check:
	PYTHONPATH=. ./.venv/bin/python3 ./scripts/check_sitl.py

repl:
	PYTHONSTARTUP="$(CURDIR)/.pythonstartup.py" ./.venv/bin/python3

uav-sitl:
	docker build -t uav-sitl sitl

rm-uav-sitl:
	docker image rm uav-sitl

ardupilotmega:
	nvim "$$(./.venv/bin/python3 -c 'import pymavlink; from pathlib import Path; print(Path(pymavlink.__file__).parent / "dialects/v20/ardupilotmega.py")')"
