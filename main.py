from argparse import ArgumentParser


def args():
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", required=False, default=8080, type=int,
                        help="The port that the proxy server listen on.")
    return parser.parse_args()


def main():
    from server import ProxyServer
    argv = args()
    ProxyServer(port=argv.port).start()


if __name__ == '__main__':
    main()
