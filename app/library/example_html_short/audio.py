import json, numpy as np
from scipy.io import wavfile
p=json.load(open("project.json")); SR=48000; N=int(round(p["nfr"]/p["fps"]*SR)); t=np.arange(N)/SR
x=np.zeros(N)
for s in p["scenes"][1:]:
    x+=np.exp(-((t-s[1])/0.12)**2)*np.random.default_rng(int(s[1]*10)).standard_normal(N)*0.05
wavfile.write("mix.wav",SR,np.stack([x,x],1).astype(np.float32))
