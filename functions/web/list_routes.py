from web.api_server import app

def main():
    print("Registered routes (rule -> methods):")
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        print(f"{rule.rule:40s} -> {','.join(sorted(rule.methods))}")

if __name__ == '__main__':
    main()

