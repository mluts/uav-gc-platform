.PHONY: run uav-sitl rm-uav-sitl

run: uav-sitl
	docker run -it --rm -p 5762:5762 uav-sitl

uav-sitl:
	docker build -t uav-sitl sitl

rm-uav-sitl:
	docker image rm uav-sitl
