.PHONY: run uav-sitl rm-uav-sitl

run: uav-sitl
	docker run -it --rm -p 127.0.0.1:5762:5762 uav-sitl

check-sitl:
	./.venv/bin/python3 ./scripts/check_sitl.py

py-stubs:
	pyright --createstub pymavlink

uav-sitl:
	docker build -t uav-sitl sitl

rm-uav-sitl:
	docker image rm uav-sitl
