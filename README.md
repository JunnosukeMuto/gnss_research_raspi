# gnss_research_raspi

## cmake

```sh
mkdir build
cd build
cmake ..
make
```

## ntrip

```sh
curl -v https://ntrip.go.gnss.go.jp:443 -u {username}:{password} --header "Ntrip-Version: Ntrip/2.0" --header "User-Agent: NTRIP curl"
```
