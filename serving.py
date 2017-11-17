import os

import numpy as np
import tensorflow as tf

import data_helpers
from multi_class_data_loader import MultiClassDataLoader
from word_data_processor import WordDataProcessor

tf.flags.DEFINE_integer("batch_size", 256, "Batch Size (default: 64)")
# tf.flags.DEFINE_string("checkpoint_dir", "./runs/1509332332/checkpoints/", "")
# tf.flags.DEFINE_string("checkpoint_dir", "./runs/1510118340/checkpoints/", "")
tf.flags.DEFINE_string("checkpoint_dir", "", "Checkpoint directory from training run")
tf.flags.DEFINE_boolean("eval_train", False, "Evaluate on all training data")

tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")
tf.flags.DEFINE_boolean("model_version", 2, "")

data_loader = MultiClassDataLoader(tf.flags, WordDataProcessor())
data_loader.define_flags()

FLAGS = tf.flags.FLAGS
FLAGS._parse_flags()
print("\nParameters:")
for attr, value in sorted(FLAGS.__flags.items()):
    print("{}={}".format(attr.upper(), value))
print("")

# if FLAGS.eval_train:
#     x_raw, y_test = data_loader.load_data_and_labels()
#     y_test = np.argmax(y_test, axis=1)
# else:
#     x_raw, y_test = data_loader.load_dev_data_and_labels()
#     y_test = np.argmax(y_test, axis=1)

# checkpoint_dir이 없다면 가장 최근 dir 추출하여 셋팅
if FLAGS.checkpoint_dir == "":
    all_subdirs = ["./runs/" + d for d in os.listdir('./runs/.') if os.path.isdir("./runs/" + d)]
    latest_subdir = max(all_subdirs, key=os.path.getmtime)
    FLAGS.sub_dir = latest_subdir
    FLAGS.checkpoint_dir = latest_subdir + "/checkpoints/"

# # Map data into vocabulary
# vocab_path = os.path.join(FLAGS.checkpoint_dir, "..", "vocab")
# vocab_processor = data_loader.restore_vocab_processor(vocab_path)
# x_test = np.array(list(vocab_processor.transform(x_raw)))

# ==================================================
checkpoint_file = tf.train.latest_checkpoint(FLAGS.checkpoint_dir)
graph = tf.Graph()
with graph.as_default():
    session_conf = tf.ConfigProto(
        allow_soft_placement=FLAGS.allow_soft_placement,
        log_device_placement=FLAGS.log_device_placement)
    sess = tf.Session(config=session_conf)
    with sess.as_default():
        # export_path = os.path.join(
        #     tf.compat.as_bytes(export_path_base))
        export_path = os.path.abspath(os.path.join(FLAGS.sub_dir, "serving", str(FLAGS.model_version)))
        print('Exporting trained model to \n', export_path)
        builder = tf.saved_model.builder.SavedModelBuilder(export_path)

        saver = tf.train.import_meta_graph("{}.meta".format(checkpoint_file))
        saver.restore(sess, checkpoint_file)

        input_x = graph.get_operation_by_name("input_x").outputs[0]
        input_y = graph.get_operation_by_name("input_y").outputs[0]
        predictions = graph.get_operation_by_name("output/predictions").outputs[0]

        # dropout_keep_prob = graph.get_operation_by_name("dropout_keep_prob").outputs[0]
        # phase_train = graph.get_operation_by_name("phase_train").outputs[0]
        #
        # batches = data_helpers.batch_iter(list(x_test), FLAGS.batch_size, 1, shuffle=False)
        #
        # all_predictions = []
        #
        # for x_test_batch in batches:
        #     batch_predictions = sess.run(predictions,
        #                                  {input_x: x_test_batch, dropout_keep_prob: 1.0, phase_train: False})
        #     all_predictions = np.concatenate([all_predictions, batch_predictions])

        # serialized_tf_example = tf.placeholder(tf.string, name='tf_example')
        # v,idx = tf.nn.top_k(y_test, [])

        # {input_x: x_test, input_y: y_test, predictions: all_predictions}
        classification_inputs = tf.saved_model.utils.build_tensor_info(
            input_x
        )
        classification_outputs_classes = tf.saved_model.utils.build_tensor_info(
            input_y
        )
        classification_outputs_scores = tf.saved_model.utils.build_tensor_info(
            predictions
        )

        classification_signature = (
            tf.saved_model.signature_def_utils.build_signature_def(
                inputs={
                    tf.saved_model.signature_constants.CLASSIFY_INPUTS:
                        classification_inputs
                },
                outputs={
                    tf.saved_model.signature_constants.CLASSIFY_OUTPUT_CLASSES:
                        classification_outputs_classes,
                    tf.saved_model.signature_constants.CLASSIFY_OUTPUT_SCORES:
                        classification_outputs_scores
                },
                method_name=tf.saved_model.signature_constants.CLASSIFY_METHOD_NAME))

        tensor_info_x = tf.saved_model.utils.build_tensor_info(input_x)
        tensor_info_y = tf.saved_model.utils.build_tensor_info(input_y)

        prediction_signature = (
            tf.saved_model.signature_def_utils.build_signature_def(
                inputs={'images': tensor_info_x},
                outputs={'scores': tensor_info_y},
                method_name="positive_negative"))
        # method_name=tf.saved_model.signature_constants.PREDICT_METHOD_NAME))

        legacy_init_op = tf.group(tf.tables_initializer(), name='legacy_init_op')

        builder.add_meta_graph_and_variables(
            sess, [tf.saved_model.tag_constants.SERVING],
            signature_def_map={
                'predict_images':
                    prediction_signature,
                tf.saved_model.signature_constants.DEFAULT_SERVING_SIGNATURE_DEF_KEY:
                    classification_signature,
            },
            legacy_init_op=legacy_init_op)

        builder.save()

        print("Done exporting!")