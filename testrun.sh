while true; do python example.py -u opc.tcp://10.10.10.13:4840  -p '0:Objects, 2:DeviceSet, 4:rfr310' 'magicwordxx' | tail -1; sleep 1; done
