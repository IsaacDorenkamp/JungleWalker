### BUILT-IN METHODS SCRIPT ###

import math

def Average( data ):
    console = data.GetConsole()
    
    A = data.GetA()
    B = data.GetB()
    spec = data.GetSpeciesList()
    workspace = data.GetWorkspace()

    console.WriteLine("Calculating average activity levels...")
    
    res = {}
    entries = len(A[spec[0]])
    for i in spec:
        res[i] = []
        for idx in xrange(0, entries):
            A_val = A[i][idx]
            B_val = B[i][idx]
            res[i].append((A_val + B_val) / 2)

    console.WriteLine("Writing results...")

    outputs = workspace.GetFile( "outputs.csv" )
    outputs.write( data.ToCSV(res) )
    outputs.close()

    console.WriteLine("Results written.")

# Confidence Interval (CI) Analysis Method
def _quantile(dataset, q):
    # Calculate the "q" percentile of dataset.
    # Linear interpolation is used when the quantile
    # lies between two elements of dataset.
    
    if q > 1.0 or q < 0.0:
	raise ValueError("Quantile must be between 0.0 and 1.0!")
    if len(dataset) == 0:
	return 0
    dataset = list(dataset)
    dataset.sort()
    idx = ((len(dataset) - 1) * q)

    if math.floor(idx) != idx:
	f_idx = int(math.floor(idx))
	return (dataset[f_idx] + (dataset[f_idx+1] - dataset[f_idx])*(idx - f_idx))
    else:
	return (dataset[int(idx)])

def CIAnalysis( data ):
    console = data.GetConsole()
    console.WriteRawLine("> Calculating 95% confidence intervals...")
    _CIAnalysis( data, 0.95 )
    console.WriteRawLine("> Calculating 99.95% confidence intervals...")
    _CIAnalysis( data, 0.9995 )
    console.WriteRawLine("All confidence intervals calculated.")

def _CIAnalysis( data, perc ):
    A = data.GetA()
    B = data.GetB()
    spec = []
    for i in data.GetSpeciesList():
        if i in B:
            spec.append(i)

    console = data.GetConsole() # get the interactive console object to keep track of progress

    console.WriteRawLine("")

    console.WriteLine("Calculating average activity levels...")

    # start by calculating the average percentage
    # of each protein for both input data sets.
    A_avg = {}
    B_avg = {}
    for i in spec:
        A_avg[i] = sum(A[i]) / len(A[i])
        B_avg[i] = sum(B[i]) / len(B[i])

    console.WriteLine("Calculating Percentiles (%.02f%%-%.02f%%)..." % ( perc*100, (1.0-perc)*100 ))

    # calculate percentiles
    A_quant = {}
    B_quant = {}
    for i in spec:
        A_quant[i] = (_quantile( A[i], perc ), _quantile( A[i], 1.0 - perc ))
        B_quant[i] = (_quantile( B[i], perc ), _quantile( B[i], 1.0 - perc ))

    console.WriteLine("Calculating confidence intervals...")

    entries = []
    for i in spec:
        A_top    = A_quant[i][0]
        A_bottom = A_quant[i][1]
        B_top    = B_quant[i][0]
        B_bottom = B_quant[i][1]

        name = data.GetSpeciesName(i)

        if B_bottom == 0 and A_top == 0:
            if A_avg[i] > 0:
                _min = -100
            else:
                _min = 0
        else:
            if A_top == 0:
                _min = (B_bottom * 10) * 100
            else:
                _min = ((B_bottom - A_top) / A_top) * 100 # regular formula. This is the standard method of calculating the minimum.

        if B_top == 0 and A_bottom == 0:
            if B_avg[i] > 0:
                _max = (B_avg[i]*10) * 100
            else:
                _max = 0
        else:
            if A_bottom == 0:
                _max = (B_top*10) * 100
            else:
                _max = ((B_top - A_bottom) / A_bottom) * 100 # regular formula. This is the standard method of calculating the maximum.

        temp = _max
        _max = max(_min, _max)
        _min = min(_min, temp)
                
        _avg = ((_min + _max) / 2)
        entries.append(("Node: %s\nAverage Activity Level in A: %0.2f%%\nAverage Activity Level in B: %0.2f%%\n\
CI Minimum: %0.2f%%\nCI Maximum: %0.2f%%\nCI Average: %0.2f%%" % (name, A_avg[i], B_avg[i], _min, _max, _avg), name))

    console.WriteLine("Collating results...")

    # Produce Output

    entries.sort(key=lambda x: x[1].lower())
    out = '\n\n'.join( [x[0] for x in entries] )

    console.WriteLine("Writing results...")

    ws = data.GetWorkspace()
    if math.floor(perc*100) == perc*100:
        tail = str(int(perc * 100))
    else:
        tail = str(perc*100)
    f = ws.GetFile('CIAnalysis_%s.txt' % tail)
    f.write(out)
    f.close()

    console.WriteLine("Results written.")

    console.WriteRawLine("")

def ExportToFile( data ):
    console = data.GetConsole()
    console.WriteLine("Collecting activity levels of outputs...")
    
    A = data.GetA()
    
    res_set = {}
    for i in A.keys():
        nm = data.GetSpeciesName(i)
        res_set[nm] = A[i]

    csv_out = data.ToCSV(res_set)
    output_f = data.GetWorkspace().GetFile("outputs.csv")
    output_f.write(csv_out)
    output_f.close()

    del res_set

    console.WriteLine("Collecting activity levels of inputs...")

    # Now for the inputs
    A_i = data.GetInputAData()
    
    res_set = {}
    for i in A_i.keys():
        nm = data.GetSpeciesName(i)
        res_set[nm] = A_i[i]

    console.WriteLine("Writing results...")

    csv_in = data.ToCSV(res_set)
    output_f = data.GetWorkspace().GetFile("inputs.csv")
    output_f.write(csv_in)
    output_f.close()

    console.WriteLine("Results written.")

NAME = 'Built-in Methods'
REGISTER = {
    'Average': (Average, True),
    'Confidence Interval Analysis': (CIAnalysis, True),
    'Export To File': (ExportToFile, False)
}
