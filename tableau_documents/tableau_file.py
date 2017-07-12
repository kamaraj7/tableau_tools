# -*- coding: utf-8 -*-

import zipfile
import os
import shutil
from ..tableau_base import *
from tableau_datasource import TableauDatasource
from tableau_workbook import TableauWorkbook
from tableau_document import TableauDocument


class TableauFile(TableauBase):

    def __init__(self, filename, logger_obj=None):
        """
        :type filename: unicode
        :type logger_obj: Logger
        """
        self.logger = logger_obj
        self.log(u'TableauFile initializing for {}'.format(filename))
        self.packaged_file = False
        self.packaged_filename = None
        self.tableau_xml_file = None
        self._tableau_document = None
        self._file_type = None
        self.other_files = []
        self.temp_filename = None
        if filename.lower().find(u'.tdsx') != -1:
            self._file_type = u'tdsx'
            self.packaged_file = True
        elif filename.lower().find(u'.twbx') != -1:
            self._file_type = u'twbx'
            self.packaged_file = True
        elif filename.lower().find(u'.twb') != -1:
            self._file_type = u'twb'
        elif filename.lower().find(u'.tds') != -1:
            self._file_type = u'tds'
        else:
            raise InvalidOptionException(u'Must open a Tableau file with ending of tds, tdsx, twb, or twbx')
        try:
            file_obj = open(filename, 'rb')
        except IOError:
            self.log(u"Cannot open file {}".format(filename))
            raise

        self.log(u'File type is {}'.format(self.file_type))
        # Extract the TWB or TDS file to disk, then create a sub TableauFile
        if self.file_type in [u'twbx', u'tdsx']:
            self.zf = zipfile.ZipFile(file_obj)
            # Ignore anything in the subdirectories
            for name in self.zf.namelist():
                if name.find('/') == -1:
                    if name.endswith('.tds'):
                        self.log(u'Detected a TDS file in archive, saving temporary file')
                        self.packaged_filename = os.path.basename(self.zf.extract(name))
                    elif name.endswith('.twb'):
                        self.log(u'Detected a TWB file in archive, saving temporary file')
                        self.packaged_filename = os.path.basename(self.zf.extract(name))
                else:
                    self.other_files.append(name)

            self.tableau_xml_file = TableauFile(self.packaged_filename, self.logger)
            self._tableau_document = self.tableau_xml_file.tableau_document
        elif self.file_type == u'twb':
            self._tableau_document = TableauWorkbook(filename, self.logger)
        elif self.file_type == u'tds':
            # Here we throw out metadata-records even when opening a workbook from disk, because they take up space
            # And are recreate automatically. Very similar to what we do in initialization of TableauWorkbook
            o_ds_fh = open(filename, 'rb')
            ds_fh = open(u'temp_file.txt', 'wb')
            self.temp_filename = u'temp_file.txt'
            metadata_flag = None
            for line in o_ds_fh:
                # Grab the datasources

                if line.find(u"<metadata-records") != -1 and metadata_flag is None:
                    metadata_flag = True
                if metadata_flag is not True:
                    ds_fh.write(line)
                if line.find(u"</metadata-records") != -1 and metadata_flag is True:
                    metadata_flag = False
            o_ds_fh.close()

            ds_fh.close()
            utf8_parser = etree.XMLParser(encoding='utf-8')

            ds_xml = etree.parse(u'temp_file.txt', parser=utf8_parser)

            self._tableau_document = TableauDatasource(ds_xml.getroot(), self.logger)
        self.xml_name = None
        file_obj.close()

    def __del__(self):
        if self.temp_filename is not None:
            os.remove(self.temp_filename)

    @property
    def file_type(self):
        return self._file_type

    @property
    def tableau_document(self):
        """
        :rtype: TableauDocument
        """
        return self._tableau_document

    # Appropriate extension added if needed
    def save_new_file(self, new_filename_no_extension):
        """
        :type new_filename_no_extension: unicode
        :rtype: bool
        """
        self.start_log_block()
        new_filename = new_filename_no_extension.split('.')[0]  # simple algorithm to kill extension

        if self.file_type in [u'twbx', u'tdsx']:
            save_filename = u"{}.{}".format(new_filename, self.file_type)
            new_zf = zipfile.ZipFile(save_filename, 'w')
            # Save the object down
            if self.file_type in [u'twbx', u'tdsx']:
                self.log(u'Creating temporary XML file {}'.format(self.packaged_filename))
                self.tableau_document.save_file(self.packaged_filename)
                new_zf.write(self.packaged_filename)
                os.remove(self.packaged_filename)
                self.log(u'Removed file {}'.format(self.packaged_filename))

            temp_directories_to_remove = {}
            for filename in self.other_files:
                self.log(u'Extracting file {} temporarily'.format(filename))
                self.zf.extract(filename)
                new_zf.write(filename)
                os.remove(filename)
                self.log(u'Removed file {}'.format(filename))
                lowest_level = filename.split('/')
                temp_directories_to_remove[lowest_level[0]] = True

            # Cleanup all the temporary directories
            for directory in temp_directories_to_remove:
                shutil.rmtree(directory)
            new_zf.close()
            self.zf.close()
            return True
        else:
            self.tableau_document.save_file(u"{}.{}".format(new_filename_no_extension, self.file_type))
            return True
