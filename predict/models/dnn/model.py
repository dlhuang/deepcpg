import pickle

from keras.models import CpgGraph
from keras.layers import core as kcore
from keras.layers import convolutional as kconv
from keras.layers import normalization as knorm
import keras.optimizers as kopt


def cpg_layers(params):
    layers = []
    if params.drop_in:
        layer = kcore.Dropout(params.drop_in)
        layers.append(('xd', layer))
    layer = kconv.Convolution2D(nb_filter=params.nb_filter,
                                nb_row=1,
                                nb_col=params.filter_len,
                                activation=params.activation,
                                init='glorot_uniform',
                                border_mode='same')
    layers.append(('c1', layer))
    layer = kconv.MaxPooling2D(pool_size=(1, params.pool_len))
    layers.append(('p1', layer))
    layer = kcore.Flatten()
    layers.append(('f1', layer))
    if params.drop_out:
        layer = kcore.Dropout(params.drop_out)
        layers.append(('f1d', layer))
    if params.nb_hidden:
        layer = kcore.Dense(params.nb_hidden,
                            activation='linear',
                            init='glorot_uniform')
        layers.append(('h1', layer))
        if params.batch_norm:
            layer = knorm.BatchNormalization()
            layers.append(('h1b', layer))
        layer = kcore.Activation(params.activation)
        layers.append(('h1a', layer))
        if params.drop_out:
            layer = kcore.Dropout(params.drop_out)
            layers.append(('h1d', layer))
    return layers


def seq_layers(params):
    layers = []
    if params.drop_in:
        layer = kcore.Dropout(params.drop_in)
        layers.append(('xd', layer))
    layer = kconv.Convolution1D(nb_filter=params.nb_filter,
                                filter_length=params.filter_len,
                                activation=params.activation,
                                init='glorot_uniform',
                                border_mode='same')
    layers.append(('c1', layer))
    layer = kconv.MaxPooling1D(pool_length=params.pool_len)
    layers.append(('p1', layer))
    layer = kcore.Flatten()
    layers.append(('f1', layer))
    if params.drop_out:
        layer = kcore.Dropout(params.drop_out)
        layers.append(('f1d', layer))
    if params.nb_hidden:
        layer = kcore.Dense(output_dim=params.nb_hidden,
                            activation='linear',
                            init='glorot_uniform')
        layers.append(('h1', layer))
        if params.batch_norm:
            layer = knorm.BatchNormalization()
            layers.append(('h1b', layer))
        layer = kcore.Activation(params.activation)
        layers.append(('h1a', layer))
        if params.drop_out:
            layer = kcore.Dropout(params.drop_out)
            layers.append(('h1d', layer))
    return layers


def target_layers(params):
    layers = []
    if params.nb_hidden:
        layer = kcore.Dense(params.nb_hidden,
                            activation='linear',
                            init='glorot_uniform')
        layers.append(('h1', layer))
        if params.batch_norm:
            layer = knorm.BatchNormalization()
            layers.append(('h1b', layer))
        layer = kcore.Activation(params.activation)
        layers.append(('h1a', layer))
        if params.drop_out:
            layer = kcore.Dropout(params.drop_out)
            layers.append(('h1d', layer))
    layer = kcore.Dense(1,
                        activation='sigmoid',
                        init='glorot_uniform')
    layers.append(('o', layer))
    return layers


def build(params, targets, seq_len=None, cpg_len=None, compile=True,
          nb_unit=None):
    if nb_unit is None:
        nb_unit = len(targets)

    model = CpgGraph()
    prev_nodes = []
    if params.seq:
        assert seq_len is not None, 'seq_len required!'

        def label(x):
            return 's_%s' % (x)

        layers = seq_layers(params.seq)
        prev_node = label('x')
        model.add_input(prev_node, input_shape=(seq_len, 4))
        for layer in layers:
            cur_node = label(layer[0])
            model.add_node(input=prev_node, name=cur_node, layer=layer[1])
            prev_node = cur_node
        prev_nodes.append(prev_node)

    if params.cpg:
        assert cpg_len is not None, 'cpg_len required!'

        def label(x):
            return 'c_%s' % (x)

        layers = cpg_layers(params.cpg)
        prev_node = label('x')
        model.add_input(prev_node, input_shape=(2, nb_unit, cpg_len))
        for layer in layers:
            cur_node = label(layer[0])
            model.add_node(input=prev_node, name=cur_node, layer=layer[1])
            prev_node = cur_node
        prev_nodes.append(prev_node)

    outputs = []
    for target in targets:
        def label(x):
            return '%s_%s' % (target, x)

        layers = target_layers(params.target)
        layer = layers[0]
        cur_node = label(layer[0])
        if len(prev_nodes) > 1:
            model.add_node(inputs=prev_nodes, name=cur_node, layer=layer[1])
        else:
            model.add_node(input=prev_nodes[0], name=cur_node, layer=layer[1])
        prev_node = cur_node
        layers = layers[1:]
        for layer in layers:
            cur_node = label(layer[0])
            model.add_node(input=prev_node, name=cur_node, layer=layer[1])
            prev_node = cur_node
        output = label('y')
        model.add_output(input=prev_node, name=output)
        outputs.append(output)

    if compile:
        optimizer = optimizer_from_params(params)
        loss = {output: 'binary_crossentropy' for output in outputs}
        model.compile(loss=loss, optimizer=optimizer)

    return model


def model_from_json(json_file, weights_file=None, compile=True):
    import keras.models as kmodels
    with open(json_file, 'r') as f:
        model = f.read()
    model = kmodels.model_from_json(model, compile=compile)
    model.load_weights(weights_file)
    return model


def model_from_pickle(pickle_file):
    with open(pickle_file, 'rb') as f:
        model = pickle.load(f)
    return model


def model_from_list(fnames, *args, **kwargs):
    if not isinstance(fnames, list):
        fnames = list(fnames)
    if len(fnames) == 2:
        model = model_from_json(fnames[0], fnames[1], *args, **kwargs)
    else:
        model = model_from_pickle(fnames[0])
    return model


def optimizer_from_config(config):
    optimizer_params = dict()
    for k, v in config.get('optimizer').items():
        optimizer_params[k] = v
    optimizer_name = optimizer_params.pop('name')
    optimizer = kopt.get(optimizer_name, optimizer_params)
    return optimizer


def optimizer_from_params(params):
    return kopt.get(params.optimizer, params.optimizer_params)


def copy_weights(src, dst, prefix):
    n = 0
    for k, v in src.nodes.items():
        if k.startswith(prefix) and k in dst.nodes:
            dst.nodes[k].set_weights(src.nodes[k].get_weights())
            n += 1
    return n


def model_to_pickle(model, path):
    with open(path, 'wb') as f:
        pickle.dump(model, f)


def model_to_json(model, json_file, weights_file=None):
    with open(json_file, 'w') as f:
        f.write(model.to_json())
    if weights_file is not None:
        model.save_weights(weights_file, overwrite=True)