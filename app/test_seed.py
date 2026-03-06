import traceback
import seed

try:
    seed.seed_data()
except Exception as e:
    traceback.print_exc()
