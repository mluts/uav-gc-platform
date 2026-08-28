.PHONY: run uav-sitl rm-uav-sitl check stubs

run: uav-sitl
	docker run -it --rm -p 127.0.0.1:5762:5762 uav-sitl

check:
	./.venv/bin/python3 ./scripts/check_sitl.py

stubs:
	pyright --createstub pymavlink

uav-sitl:
	docker build -t uav-sitl sitl

rm-uav-sitl:
	docker image rm uav-sitl
