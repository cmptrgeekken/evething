./run_concurrent.sh "celery worker -A evething -B -Q et_high -c 1 -n w1.%h" "celery worker -A evething -Q et_medium,et_low -c 3 -n w3.%h"
