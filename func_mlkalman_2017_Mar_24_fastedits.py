import numpy as np
import math
import numba as nb
import numpy.linalg as la

# numba wont work with np.sum(axis=), dtype=complex 128 (workaround np.complex128), str comparisons, and returning multiple values.

#@nb.jit(nopython=True)
def reconstructstate_(x_hat): # not in use
    '''Reconstructs state based on Kalman estimates.
    '''
    ans = np.sum(x_hat[::2, 0, :] + 1j*x_hat[1::2, 0, :], axis=0)
    return  ans

#@nb.jit(nopython=True)
def calc_pred_(x_hat): #not in use
    '''Reconstructs predictions based on Kalman estimates. Equivalent to reconstructstate().real()
    '''
    ans = np.sum(x_hat[::2, 0, :], axis=0)
    return  ans

@nb.jit(nopython=True)
def calc_pred(x_hat):
    '''Reconstructs predictions based on Kalman estimates. Equivalent to reconstructstate().real()
    '''
    series = x_hat.shape[2]
    pred = np.zeros(series)
    for k in xrange(series):
        pred[k] = np.sum(x_hat[::2, 0, k])
    return pred

@nb.jit(nopython=True)
def calc_Gamma(x_hat, oe, numf):
    '''Returns a vector of noise features used to calculate Q in Kalman Filtering
    '''
    Gamma2 = np.zeros((2*numf,1))
    spectralresult0=0
    spectralresult=0
    for spectralresult0 in xrange(numf):
        spectralresult = spectralresult0*2
        Gamma2[spectralresult,0] = x_hat[spectralresult,0]*(np.sqrt(oe**2/ (x_hat[spectralresult,0]**2 + x_hat[spectralresult + 1,0]**2)))
        Gamma2[spectralresult+1,0] = x_hat[spectralresult + 1,0]*(np.sqrt(oe**2/ (x_hat[spectralresult,0]**2 + x_hat[spectralresult + 1,0]**2)))   
    return Gamma2

ZERO_GAIN, PROP_FORWARD = range(2)
PredictionMethod = {
    "ZeroGain": ZERO_GAIN, 
    "PropForward": PROP_FORWARD
}

def kf_2017(y_signal, n_train, n_testbefore, n_predict, Delta_T_Sampling, x0, p0, oe, rk, freq_basis_array, phase_correction=0,prediction_method="ZeroGain"):
    '''    
    Keyword Arguments:
    ------------------
    
    y_signal -- Array containing measurements for Kalman Filtering. [Dim: 1 x num. dtype = float64]
    n_train -- Timestep at which algorithm is expected to finish learning [Scalar int]
    n_testbefore --  Predictions in  zone of msmt data [Scalar int]
    n_predict -- Predictions outside of msmt data [Scalar int]
    Delta_T_Sampling -- Time interval between measurements. [Scalar int]
    x0 -- x_hat_initial -- Initial condition for state estimate, x(0), for all basis frequencies. [Scalar int]
    p0 -- P_hat_initial -- Initial condition for state covariance estimate, P(0), for all basis frequencies. [Scalar int]
    oe -- oekalman -- Process noise covariance strength. [Scalar int] 
    rk -- rkalman -- Measurement noise covariance strength. [Scalar int]
    freq_basis_array -- Array containing basis frequencies. [Len: numf. dtype = float64]
    phase_correction -- Basis dependent + prediction method dependent. [Scalar float64]
    prediction_method -- Basis dependent.  Use Use W=0 OR PropagateForward with Phase Correction.
    
    Dimensions:
    -----------
    num -- Number of points in msmt_record. [Scalar int]
    numf -- Number of points (spectral basis frequencies) in freq_basis_array. [Scalar int]
    twonumf -- 2*numf. (NB: For each basis freq in freq_basis_array, estimators have a real and imaginary parts). [Scalar int]
    
    Known Information for Filter Design:
    -------------------------------------------------------
    
    a -- Linearised dynamic model - time invariant [Dim: twonumf x twonumf. dtype = float64]
    h -- Linear measurement action - time invariant [Dim: 1 x twonumf. dtype = float64]
    Gamma2, Gamma -- Process noise features [Dim: twonumf x 1. dtype = float64]
    Q -- Process noise covariance.[Dim: twonumf x twonumf. dtype = float64]
    R -- Measurement noise covariance; equivalent to rkalman for scalar measurement noise. [Scalar float64]
    
    
    Variables for State Estimation and State Covariance Estimation:
    ---------------------------------------------------------------
    x_hat -- Aposteriori estimates (real and estimated imaginary components of the state for each basis frequency)  [Len: twonumf. dtype = float64]
    x_hat_apriori -- Apriori estimates (real and estimated imaginary components of the state for each basis frequency) [Len: twonumf. dtype = float64]
    z_proj -- Apriori predicted measurement [Scalar float64]
    e_z -- Residuals, i.e. z - z_proj [Len: num float64]
    
    S --  Predicted output covariance estimate (i.e. uncertainty in  z_proj) [Scalar float64] 
    S_inv -- Inverse of S (NB: R must be a positive definite if S is not Scalar) [Scalar float64]
    W -- Kalman gain [Dim: twonumf x 1. dtype = float64]
    P_hat -- Aposteriori state covariance estimate (i.e. aposteriori uncertainty in estimated x_hat) [Dim: twonumf x twonumf. dtype = float64]
    P_hat_apriori -- Apriori state covariance estimate (i.e. apriori uncertainty in estimated x_hat) [Dim: twonumf x twonumf. dtype = float64]
    
    '''
    #print PredictionMethod[prediction_method]
    
    return _kf_2017(y_signal, n_train, n_testbefore, n_predict, Delta_T_Sampling, x0, p0, oe, rk, freq_basis_array, phase_correction, PredictionMethod[prediction_method])

#@nb.jit()    
def _kf_2017(y_signal, n_train, n_testbefore, n_predict, Delta_T_Sampling, x0, p0, oe, rk, freq_basis_array, phase_correction, prediction_method_):
    
    #print "did I get into filtering?"
    
    num = n_train + n_predict
    numf = len(freq_basis_array)
    twonumf = int(numf*2.0)
    
    # Kalman Measurement Data
    z = np.zeros(num)
    z[:] = y_signal

    # State Estimation
    x_hat_apriori = np.zeros((twonumf,1)) 
    x_hat = np.zeros((twonumf,1))
    e_z = np.zeros(num)
    P_hat_apriori = np.zeros((twonumf,twonumf))    
    P_hat = np.zeros((twonumf,twonumf))

    # Dynamical Model, Measurement Action and Initial Conditions
    a = np.zeros((twonumf,twonumf)) 
    h = np.zeros((1,twonumf)) 
    h[0, 0] = 1.0
    coswave = -1 
    comp = 0
    for comp in range(0,twonumf,2):
        a[comp,comp] = np.cos(Delta_T_Sampling*freq_basis_array[comp/2]*2*np.pi)
        a[comp+1,comp+1] =  np.cos(Delta_T_Sampling*freq_basis_array[comp/2]*2*np.pi)
        a[comp,comp+1] = coswave*np.sin(Delta_T_Sampling*freq_basis_array[comp/2]*2*np.pi)
        a[comp+1,comp] = -a[comp,comp+1] 

    initial = 0
    for initial in range(0,twonumf,1):
        P_hat[initial,initial] = p0 
        x_hat[initial] = x0
        if (initial % 2 == 0):
            h[0,initial] = 1.0
    
    store_x_hat = np.zeros((twonumf,1,num))
    store_P_hat = np.zeros((twonumf,twonumf,num))
    predictions = np.zeros(n_testbefore + n_predict)
    
    #h_outer = np.outer(h.T, h)
    # print "did I finish defining matrices?"
    
    k = 1
    while (k< num): 

        x_hat_apriori = np.dot(a, x_hat) 
        Gamma = np.dot(a,calc_Gamma(x_hat, oe, numf))
        Q = np.outer(Gamma, Gamma.T)
        P_hat_apriori = np.dot(np.dot(a,P_hat),a.T) + Q
        
        if prediction_method_ == ZERO_GAIN and k> (n_train):
            x_hat = x_hat_apriori
            store_x_hat[:,:,k] = x_hat
            P_hat = P_hat_apriori
            store_P_hat[:,:,k] = P_hat
            k = k+1 
            continue 

        z_proj = np.dot(h,x_hat_apriori)
        S = la.multi_dot([h,P_hat_apriori,h.T]) + rk #np.dot(np.dot(h,P_hat_apriori),h.T) + rk
        S_inv = 1.0/S #np.linalg.inv(S)
        
        if not np.isfinite(S_inv).all():
            print "Inversion Error"
            break
        
        W = np.dot(P_hat_apriori,h.T)*S_inv
        e_z[k] = z[k]-z_proj

        x_hat = x_hat_apriori + W*e_z[k]
        P_hat = P_hat_apriori - S*np.outer(W,W.T) #((S_inv**2)*la.multi_dot([P_hat_apriori,h_outer,P_hat_apriori.T]))  #np.outer(W,W.T) #((S_inv**2)*np.dot(P_hat_apriori,np.dot(h_outer,P_hat_apriori.T))) #np.outer(W,W.T) # For scalar S
        
        store_x_hat[:,:,k] = x_hat
        store_P_hat[:,:,k] = P_hat         
        
        if prediction_method_ == PROP_FORWARD and (k==n_train):
            Propagate_Foward, instantA, instantP = makePropForward(freq_basis_array, x_hat,Delta_T_Sampling,phase_correction,num,n_train,numf)
            #print "can jit return more than one thing?"
            predictions[0:n_testbefore] = calc_pred(store_x_hat[:,:,n_train-n_testbefore:n_train])
            #print "I can get here"
            predictions[n_testbefore:] = Propagate_Foward[n_train:]
            #print "how about we get here"
            #print predictions.shape # this prints
            #print predictions # this doesnt print
            return predictions #, [store_x_hat, store_P_hat, e_z, Propagate_Foward, instantA, instantP]
        
        k=k+1
    
    predictions = calc_pred(store_x_hat[:,:,n_train-n_testbefore:])
    return predictions #, [store_x_hat, store_P_hat, e_z]


def calc_phase_correction(bdelta, Delta_S_Sampling, phase_correction):
    ''' Calculates phase correction for noise traces, else returns zero.
    '''
    phase_correction_noisetraces = 0.0
    if phase_correction == 'Yes':
        phase_correction_noisetraces = (bdelta-Delta_S_Sampling)*((2*np.pi)/bdelta)
    return phase_correction_noisetraces


def calc_n_train(multiplier, bandwidth, bdelta):
    '''Calculates n_train (time step for convergence) based on input parameters.
    '''
    return int((multiplier*bandwidth)/bdelta)

#@nb.jit(nopython=True) 
def makePropForward(freq_basis_array, x_hat,Delta_T_Sampling,phase_correction_noisetraces,num,n_train,numf):
    ''' Extracts learned parameters from Kalman Filtering msmt_record and makes predictions for timesteps > n_train
    
    Keyword Arguments:
    ------------------
    freq_basis_array -- Array containing basis frequencies. [Len: numf. dtype = float64]
    x_hat -- Aposteriori KF estimates based on msmt_record (real and estimated imaginary components of the state for each basis frequency) [Len: twonumf. dtype = float64]
    Delta_T_Sampling -- Time interval between measurements. [Scalar int]
    phase_correction_noisetraces -- Applies if msmt_record data are Ramsey frequency offset measurements [Scalar float64]
    num -- Number of points in msmt_record. [Scalar int]
    n_train -- Predicted timestep at which algorithm is expected to finish learning [Scalar int]
    numf -- Number of points (spectral basis frequencies) in freq_basis_array. [Scalar int]
    
    Returns: 
    --------
    Propagate_Foward -- Output predictions. Non-zero only for n_train < timestep < num. [Len: num. dtype = float64] 
    instantA -- Instantaneous amplitude calculated based on estimated state x_hat at n_train [Len: numf. dtype = float64] 
    instantP -- Instantaneous phase calculated based on estimated state x_hat at n_train [Len: numf. dtype = float64] 
       
    '''
    #print "did I get into extraction?"
    # Instantaneous Amplitude, Phase and Frequency Calculations
    instantA = np.zeros(numf) 
    instantP = np.zeros(numf) 
    #instantW = np.zeros(numf) 
    
    # Extract Learned Parameters
    spectralresult0=0
    spectralresult=0
    for spectralresult0 in range(0,len(freq_basis_array),1):
        spectralresult = spectralresult0*2    
        instantA[spectralresult0] = np.sqrt(x_hat[spectralresult,0]**2 + x_hat[spectralresult + 1,0]**2) # using apostereroiri estimates
        #print "is it atan again?"
        instantP[spectralresult0] = math.atan2(x_hat[spectralresult + 1,0], x_hat[spectralresult,0]) # correct phase using atan2
    
    #print "Or did I make it to predictions?"
    # Make Predictions 
    Propagate_Foward = np.zeros(num)
    Harmonic_Component = 0.0
    tn = 0
    for tn in range(n_train,num,1):
        for spectralcomponent in range(0, len(freq_basis_array),1):
            if freq_basis_array[spectralcomponent] == 0:
                Harmonic_Component = instantA[spectralcomponent]*np.cos((Delta_T_Sampling*tn*freq_basis_array[spectralcomponent]*2*np.pi + instantP[spectralcomponent]))
            if freq_basis_array[spectralcomponent] != 0:
                Harmonic_Component = instantA[spectralcomponent]*np.cos((Delta_T_Sampling*tn*freq_basis_array[spectralcomponent]*2*np.pi + instantP[spectralcomponent] + phase_correction_noisetraces))
            Propagate_Foward[tn] += Harmonic_Component 
    
    #print "If I got here, then nbjit is an arse"
    return Propagate_Foward, instantA, instantP

