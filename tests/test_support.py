"""Keep module-level application initialization away from user data."""
import atexit,os,tempfile
bootstrap=tempfile.TemporaryDirectory(prefix='recalldock-tests-')
os.environ['APP_DATA_DIR']=bootstrap.name
atexit.register(bootstrap.cleanup)
