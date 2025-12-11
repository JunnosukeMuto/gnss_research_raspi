// NTRIPサーバからRTCM補正データを読み取り、その瞬間UARTでGPS-RTK2に送信するプログラム

#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>

#define SERVER_HOST "hoge.example.com"
#define SERVER_PORT 2101
#define SERVER_ENDPOINT "hoge"
#define SERVER_USER "hoge"
#define SERVER_PASS "password"

void ntrip()
{
    struct addrinfo hints;
    memset(&hints, 0, sizeof(struct addrinfo));
}