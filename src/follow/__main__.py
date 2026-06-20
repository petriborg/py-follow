"""
Launch the main loop.
Also allows for:
```bash
python -m follow ...
```
"""


if __name__ == '__main__':
    import sys
    from .main import main, setup_logging

    setup_logging('--debug' in sys.argv)
    main()
