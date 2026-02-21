import sys, traceback
print('PYTHON:', sys.executable)
print('\nSYS.PATH:')
for p in sys.path:
    print(' ', p)
print('\nTRY IMPORT DJANGO:')
try:
    import django
    print('DJANGO __file__:', getattr(django, '__file__', repr(django)))
    try:
        import django.utils
        print('django.utils import: OK')
    except Exception:
        print('django.utils import: ERROR')
        traceback.print_exc()
except Exception:
    print('Import django failed:')
    traceback.print_exc()
