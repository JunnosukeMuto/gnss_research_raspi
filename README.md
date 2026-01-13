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

## socat

```sh
socat -d -d pty,raw,echo=0 pty,raw,echo=0
```

```sh
echo -ne '$GPGGA,092725.00,4717.11399,N,00833.91590,E,1,08,1.01,499.6,M,48.0,M,,*5B\r\n' > /dev/pts/4
```
