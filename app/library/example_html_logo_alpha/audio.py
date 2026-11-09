import numpy as np
from scipy.io import wavfile
SR=48000; N=3*SR; t=np.arange(N)/SR
x=np.sin(2*np.pi*(200+600*t)*t)*np.exp(-((t-0.6)/0.4)**2)*0.15
wavfile.write("mix.wav",SR,np.stack([x,x],1).astype(np.float32))
