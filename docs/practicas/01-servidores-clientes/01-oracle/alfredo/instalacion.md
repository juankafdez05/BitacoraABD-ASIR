# Instalación de Oracle Database 26ai Enterprise en Debian 13(mediante Gold Image) (Por Alfredo)
Esta guía detalla el procedimiento para preparar el sistema operativo e instalar Oracle Database 26ai Enterprise Edition (instalación mediante *gold image* y creación de una base de datos contenedora CDB con PDB) en un entorno Debian 13 (Trixie).

> **Atención**: Debian no es una distribución oficialmente certificada por Oracle. La instalación requiere deshabilitar la validación estricta del instalador mediante la variable `CV_ASSUME_DISTID=OL8` y la opción `-ignorePrereqFailure`.

## 1. Requisitos Mínimos y Preparación del Sistema Operativo

Antes de comenzar el despliegue, el servidor debe cumplir con los siguientes recursos mínimos exigidos por Oracle Database:

* **Memoria RAM**: Mínimo 2 GB (recomendado 8 GB o superior).

* **Memoria de Intercambio (SWAP)**:

  * Igual a la RAM si está entre 2 GB y 16 GB.

  * 16 GB fijos si la RAM es superior a 16 GB.

* **Espacio en Disco**: Al menos 10 GB de espacio libre para el software (`ORACLE_HOME`), espacio adicional para la base de datos (`/u01/oradata`) y mínimo 1 GB libre en `/tmp`.

* **Resolución de nombres**: FQDN asignado correctamente en `/etc/hosts`.

### Instalación de paquetes y adaptación de librerías en Debian

En primer lugar, se instalan todas las herramientas de compilación, enlazado, shells y bibliotecas del sistema necesarias para que el instalador de Oracle pueda reconstruir los binarios adecuadamente.

```
sudo apt update
sudo apt install -y \
  binutils gcc g++ make libc6-dev \
  libaio-dev libaio1t64 libnsl2 libstdc++6 \
  libelf-dev elfutils ksh bc unzip \
  net-tools sysstat psmisc lsof \
  libxi6 libxtst6 libxrender1 \
  rlwrap

```

En Debian 13 el paquete de la biblioteca `libaio1` se empaqueta como `libaio1t64` (`libaio.so.1t64`), pero el instalador de Oracle busca explícitamente el nombre tradicional `libaio.so.1`. Creamos el enlace simbólico y actualizamos la caché de bibliotecas.

```
sudo ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1
sudo ldconfig

```

Comprobamos que las bibliotecas críticas quedan bien resueltas:

```
sudo ldconfig -p | grep -E 'libaio|libnsl'

```

```
debian@oracle:~$ sudo ldconfig -p | grep -E 'libaio|libnsl'
	libnsl.so.2 (libc6,x86-64) => /lib/x86_64-linux-gnu/libnsl.so.2
	libnsl.so.1 (libc6,x86-64) => /lib/x86_64-linux-gnu/libnsl.so.1
	libaio.so.1t64 (libc6,x86-64) => /lib/x86_64-linux-gnu/libaio.so.1t64
	libaio.so (libc6,x86-64) => /lib/x86_64-linux-gnu/libaio.so


```

### Resolución de nombres de red

Configuramos el FQDN del servidor y aseguramos que apunte a la IP estática en el archivo `/etc/hosts` para evitar fallos de red durante la configuración del Listener.

```
sudo hostnamectl set-hostname ora26ai.example.com
echo "TU_IP   ora26ai.example.com   ora26ai" | sudo tee -a /etc/hosts

```

Verificamos la resolución:

```
hostname -f
getent hosts ora26ai.example.com

```

```
debian@oracle:~$ hostname -f
ora26ai.example.com
debian@oracle:~$ getent hosts ora26ai.example.com
fe80::5054:ff:feb8:8b28 ora26ai.example.com


```

## 2. Configuración de Usuarios, Kernel y Directorios Estándar (OFA)

### Grupos y usuario de sistema

De acuerdo con las recomendaciones de la guía oficial de instalación de Oracle, creamos el grupo primario para la instalación (`oinstall`), el grupo de administración (`dba`) y el usuario de sistema `oracle` asignado a ambos.

```
sudo groupadd -g 54321 oinstall
sudo groupadd -g 54322 dba
sudo useradd -m -u 54321 -g oinstall -G dba -s /bin/bash oracle
sudo passwd oracle

```

Verificamos la creación del usuario:

```
id oracle

```

```
debian@oracle:~$ id oracle
uid=54321(oracle) gid=54321(oinstall) groups=54321(oinstall),54322(dba)


```

### Parámetros del kernel y límites del sistema

Añadimos los parámetros de memoria compartida, semáforos, descriptores de archivos y rangos de puertos efímeros en `/etc/sysctl.conf` para cumplir con las especificaciones del motor de Oracle.

```
sudo tee -a /etc/sysctl.conf <<'EOF'

# Oracle Database 26ai
fs.file-max = 6815744
fs.aio-max-nr = 1048576
kernel.sem = 250 32000 100 128
kernel.shmmni = 4096
kernel.shmall = 1073741824
kernel.shmmax = 4398046511104
kernel.panic_on_oops = 1
net.core.rmem_default = 262144
net.core.rmem_max = 4194304
net.core.wmem_default = 262144
net.core.wmem_max = 1048576
net.ipv4.ip_local_port_range = 9000 65500
EOF
sudo sysctl -p

```

```
debian@oracle:~$ sudo sysctl -p
fs.file-max = 6815744
fs.aio-max-nr = 1048576
kernel.sem = 250 32000 100 128
kernel.shmmni = 4096
kernel.shmall = 1073741824
kernel.shmmax = 4398046511104
kernel.panic_on_oops = 1
net.core.rmem_default = 262144
net.core.rmem_max = 4194304
net.core.wmem_default = 262144
net.core.wmem_max = 1048576
net.ipv4.ip_local_port_range = 9000 65500


```

A continuación, definimos los límites de recursos de procesos, archivos abiertos y pila para el usuario `oracle` en `/etc/security/limits.conf`.

```
sudo tee -a /etc/security/limits.conf <<'EOF'

# Oracle Database 26ai
oracle   soft   nofile    1024
oracle   hard   nofile    65536
oracle   soft   nproc     16384
oracle   hard   nproc     16384
oracle   soft   stack     10240
oracle   hard   stack     32768
oracle   soft   memlock   134217728
oracle   hard   memlock   134217728
EOF

```

Aseguramos que el módulo `pam_limits` se aplique en sesiones de cambio de usuario e inspeccionamos los límites efectivos:

```
sudo sed -i 's/^#\s*\(session\s\+required\s\+pam_limits.so\)/\1/' /etc/pam.d/su
sudo su - oracle -c 'ulimit -n -u -s'

```

```
debian@oracle:~$ sudo su - oracle -c 'ulimit -n -u -s'
open files                          (-n) 1024
max user processes                  (-u) 16384
stack size                  (kbytes, -s) 10240


```

### Directorios OFA y variables de entorno

Creamos los directorios de instalación según la arquitectura OFA (Oracle Flexible Architecture) asignándoles el propietario y permisos correspondientes.

```
sudo mkdir -p /u01/app/oracle/product/26.0.0/dbhome_1
sudo mkdir -p /u01/app/oraInventory
sudo mkdir -p /u01/oradata
sudo mkdir -p /u01/fast_recovery_area
sudo chown -R oracle:oinstall /u01
sudo chmod -R 775 /u01

```

Configuramos las variables de entorno del usuario `oracle` en su archivo `~/.bashrc`. Destaca la variable `CV_ASSUME_DISTID=OL8`, indispensable para omitir la comprobación de distribución no soportada en Debian.

```
sudo tee -a /home/oracle/.bashrc <<'EOF'

# Oracle Database 26ai
export TMP=/tmp
export TMPDIR=$TMP
export ORACLE_HOSTNAME=ora26ai.example.com
export ORACLE_BASE=/u01/app/oracle
export ORACLE_HOME=$ORACLE_BASE/product/26.0.0/dbhome_1
export ORACLE_SID=ORCL
export ORACLE_UNQNAME=ORCL
export DATA_DIR=/u01/oradata
export PATH=$ORACLE_HOME/bin:$ORACLE_HOME/OPatch:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib:/lib:/usr/lib
export CLASSPATH=$ORACLE_HOME/jlib:$ORACLE_HOME/rdbms/jlib
export NLS_LANG=AMERICAN_AMERICA.AL32UTF8
export CV_ASSUME_DISTID=OL8
alias sqlp='rlwrap sqlplus / as sysdba'
EOF
sudo chown oracle:oinstall /home/oracle/.bashrc

```

Tras esto, es necesario ejecutar el sed a continuación ya que Debian mete por defecto en todos los .bashrc un bloque que bloquea la ejecución del contenido de estos en shell no interactivas, así que es sed elimina dicho bloque para que no nos estorbe en comandos que expanden sub shells que ejecutaremos durante la instalación.

```
sudo sed -i '/# If not running interactively/,/esac/d' /home/oracle/.bashrc

```

Verificamos las variables de entorno cargadas:

```
sudo su - oracle -c 'env | grep -E "ORACLE|CV_ASSUME"'

```

```
debian@oracle:~$ sudo su - oracle -c 'env | grep -E "ORACLE|CV_ASSUME"'
ORACLE_BASE=/u01/app/oracle
ORACLE_HOME=/u01/app/oracle/product/26.0.0/dbhome_1
ORACLE_HOSTNAME=ora26ai.example.com
ORACLE_UNQNAME=ORCL
CV_ASSUME_DISTID=OL8
ORACLE_SID=ORCL


```

>**Importante**: Hemos declarado todas las variables de entorno y el path en el `.bashrc` del usuario oracle ya que queremos que estas estén solo disponibles para el. Esto conlleva que para los demás usuarios del sistema, los binarios de oracle tampoco están en el path, lo que no nos importa ya que nadie se conectara a la base desde el propio servidor. En caso de que si quisiésemos que usuarios puedan acceder desde el servidor, podríamos agregar también el path globalmente (aunque no consideramos esto buena practica en el servidor):

```
sudo cat << 'EOF' | sudo tee /etc/profile.d/oracle.sh
export PATH=$ORACLE_HOME/bin:$ORACLE_HOME/OPatch:$PATH
alias sqlp='rlwrap sqlplus / as sysdba'
EOF

```

## 3. Instalación del Software y Creación de la Base de Datos

### Descompresión de la imagen de oracle e instalación silenciosa

Descomprimimos el paquete de instalación directamente en la ruta del `$ORACLE_HOME` usando el usuario `oracle`.(Este paquete tendríamos que haberlo descargado de antemano, podemos obtenerlo en [la web oficial de oracle](https://www.oracle.com/es/database/technologies/oracle-database-software-downloads.html))

```
sudo su - oracle -c 'unzip -q /TU_DIRECTORIO/LINUX.X64_2326100_db_home.zip -d /u01/app/oracle/product/26.0.0/dbhome_1'

```

Tras esto es conveniente eliminar el fichero original de la imagen.

```
rm -f /TU_DIRECTORIO/LINUX.X64_2326100_db_home.zip
```

Iniciamos la instalación silenciosa indicando únicamente la instalación del motor de software (`INSTALL_DB_SWONLY`). Omitimos las advertencias de prerequisitos con `-ignorePrereqFailure`.

```
sudo su - oracle -c 'cd /u01/app/oracle/product/26.0.0/dbhome_1 && ./runInstaller -silent -ignorePrereqFailure \
  oracle.install.option=INSTALL_DB_SWONLY \
  UNIX_GROUP_NAME=oinstall \
  INVENTORY_LOCATION=/u01/app/oraInventory \
  ORACLE_BASE=/u01/app/oracle \
  oracle.install.db.InstallEdition=EE \
  oracle.install.db.OSDBA_GROUP=dba \
  oracle.install.db.OSOPER_GROUP=dba \
  oracle.install.db.OSBACKUPDBA_GROUP=dba \
  oracle.install.db.OSDGDBA_GROUP=dba \
  oracle.install.db.OSKMDBA_GROUP=dba \
  oracle.install.db.OSRACDBA_GROUP=dba \
  SECURITY_UPDATES_VIA_MYORACLESUPPORT=false \
  DECLINE_SECURITY_UPDATES=true'

```

```
debian@oracle:~$ sudo su - oracle -c 'cd /u01/app/oracle/product/26.0.0/dbhome_1 && ./runInstaller -silent -ignorePrereqFailure ...'
Launching Oracle AI Database Setup Wizard...

[WARNING] [INS-13001] Oracle Database is not supported on this operating system. Installer will not perform prerequisite checks on the system.
   CAUSE: This operating system may not have been in the certified list at the time of the release of this software.
   ACTION: Refer to My Oracle Support portal for the latest certification information for this operating system. Proceed with the installation if the operating system has been certified after the release of this software.
The response file for this session can be found at:
 /u01/app/oracle/product/26.0.0/dbhome_1/install/response/db_2026-10-06_07-47-55AM.rsp

You can find the log of this install session at:
 /tmp/InstallActions2026-10-06_07-47-55AM/installActions2026-10-06_07-47-55AM.log

As a root user, run the following script(s):
	1. /u01/app/oraInventory/orainstRoot.sh
	2. /u01/app/oracle/product/26.0.0/dbhome_1/root.sh

Run /u01/app/oraInventory/orainstRoot.sh on the following nodes:
[ora26ai]
Run /u01/app/oracle/product/26.0.0/dbhome_1/root.sh on the following nodes:
[ora26ai]


Successfully Setup Software.
Moved the install session logs to:
 /u01/app/oraInventory/logs/InstallActions2026-10-06_07-47-55AM


```

Finalizada la instalación del software, ejecutamos los scripts de registro y permisos con privilegios elevados (`sudo`).

```
sudo /u01/app/oraInventory/orainstRoot.sh
sudo /u01/app/oracle/product/26.0.0/dbhome_1/root.sh

```

```
debian@oracle:~$ sudo /u01/app/oraInventory/orainstRoot.sh
Changing permissions of /u01/app/oraInventory.
Adding read,write permissions for group.
Removing read,write,execute permissions for world.

Changing groupname of /u01/app/oraInventory to oinstall.
The execution of the script is complete.
debian@oracle:~$ sudo /u01/app/oracle/product/26.0.0/dbhome_1/root.sh
Check /u01/app/oracle/product/26.0.0/dbhome_1/install/root_ora26ai.example.com_2026-10-06_07-49-14-820754055.log for the output of root script


```

Comprobamos que el software se registró correctamente en el inventario:

```
sudo su - oracle -c 'sqlplus -V'
sudo cat /u01/app/oraInventory/ContentsXML/inventory.xml

```

```
debian@oracle:~$ sudo su - oracle -c 'sqlplus -V'

SQL*Plus: Release 23.26.1.0.0 - Production
Version 23.26.1.0.0
debian@oracle:~$ sudo cat /u01/app/oraInventory/ContentsXML/inventory.xml
<?xml version="1.0" standalone="yes" ?>
<!-- Copyright (c) 1999, 2026, Oracle and/or its affiliates.
All rights reserved. -->
<!-- Do not modify the contents of this file by hand. -->
<INVENTORY>
<VERSION_INFO>
   <SAVED_WITH>12.2.0.9.0</SAVED_WITH>
   <MINIMUM_VER>2.1.0.6.0</MINIMUM_VER>
</VERSION_INFO>
<HOME_LIST>
<HOME NAME="OraDB23Home1" LOC="/u01/app/oracle/product/26.0.0/dbhome_1" TYPE="O" IDX="1"/>
</HOME_LIST>
<COMPOSITEHOME_LIST>
</COMPOSITEHOME_LIST>
</INVENTORY>


```

### Configuración del Listener y Despliegue de la Base de Datos (CDB/PDB)

Con el usuario `oracle`, creamos el Listener predeterminado escuchando en el puerto 1521 usando `netca`.

```
sudo su - oracle -c '$ORACLE_HOME/bin/netca -silent -responsefile $ORACLE_HOME/assistants/netca/netca.rsp'
sudo su - oracle -c '$ORACLE_HOME/bin/lsnrctl status'

```

```
debian@oracle:~$ sudo su - oracle -c '$ORACLE_HOME/bin/netca -silent -responsefile $ORACLE_HOME/assistants/netca/netca.rsp'

Parsing command line arguments:
    Parameter "silent" = true
    Parameter "responsefile" = /u01/app/oracle/product/26.0.0/dbhome_1/assistants/netca/netca.rsp
Done parsing command line arguments.
Oracle Net Services Configuration:
Profile configuration complete.
Oracle Net Listener Startup:
    Running Listener Control:
      /u01/app/oracle/product/26.0.0/dbhome_1/bin/lsnrctl start LISTENER
    Listener Control complete.
    Listener started successfully.
Listener configuration complete.
Oracle Net Services configuration successful. The exit code is 0
debian@oracle:~$ sudo su - oracle -c '$ORACLE_HOME/bin/lsnrctl status'

LSNRCTL for Linux: Version 23.26.1.0.0 - Production on 06-OCT-2026 07:49:31

Copyright (c) 1991, 2026, Oracle.  All rights reserved.

Connecting to (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=ora26ai.example.com)(PORT=1521)))
STATUS of the LISTENER
------------------------
Alias                     LISTENER
Version                   TNSLSNR for Linux: Version 23.26.1.0.0 - Production
Start Date                06-OCT-2026 07:49:31
Uptime                    0 days 0 hr. 0 min. 0 sec
Trace Level               off
Security                  ON: Local OS Authentication
SNMP                      OFF
Listener Parameter File   /u01/app/oracle/product/26.0.0/dbhome_1/network/admin/listener.ora
Listener Log File         /u01/app/oracle/diag/tnslsnr/ora26ai/listener/alert/log.xml
Listening Endpoints Summary...
  (DESCRIPTION=(ADDRESS=(PROTOCOL=tcp)(HOST=ora26ai.example.com)(PORT=1521)))
  (DESCRIPTION=(ADDRESS=(PROTOCOL=ipc)(KEY=EXTPROC1521)))
The listener supports no services
The command completed successfully


```

#### Fundamentos de la Arquitectura Multitenant (CDB y PDB)

A partir de las versiones modernas de Oracle Database, la arquitectura **Multitenant** es el estándar obligatorio para desplegar bases de datos. Se compone de dos elementos principales:

* **Container Database (CDB):** Es la base de datos contenedora o raíz. Corresponde a la instancia física real que administra los procesos de segundo plano del sistema operativo, asigna la memoria RAM (SGA y PGA), gestiona los archivos de control y alberga el Diccionario de Datos global (`CDB$ROOT`).

* **Pluggable Database (PDB):** Es una base de datos enchufable o portátil que reside dentro de la CDB. Representa el entorno lógico dedicado a la aplicación, alojando los esquemas, tablas e índices del usuario en completo aislamiento de otras PDBs.

**¿Por qué es obligatorio configurar ambas?**
Oracle ha descontinuado el modelo tradicional no contenedor (*Non-CDB*). Para cumplir con los requerimientos del motor y las mejores prácticas de administración:

1. El contenedor raíz (`CDB$ROOT`) está reservado exclusivamente para los metadatos y tareas globales de Oracle; el sistema prohíbe crear tablas de aplicación directamente en él.

2. Es indispensable crear al menos **una PDB activa** (como `PDB1`) para almacenar la información de los usuarios y garantizar la separación entre la infraestructura de la base de datos y los datos de negocio.

Antes de poder ejecutar el binario dbca para crear la bd, como nos encontramos en Debian y no en un sistema basado en redhat, es necesario que creemos un synlink de /bin/true como /bin/rpm ya que dbca usa este binario para comprobar requisitos del sistema antes de hacer nada, así que como sabemos que todas las dependencias ya están presentes usaremos este truco para saltarnos la verificación y que no nos de error.
    
```
sudo ln -sf /bin/true /bin/rpm
```

A continuación, ejecutamos `dbca` en modo silencioso para crear la base de datos contenedora `ORCL` (CDB) junto con la Pluggable Database inicial `PDB1`. (Podemos modificar parametros como totalMemory a los requerimientos del sistema, en este caso lo e dejado 3GB ya que la ram maxima del sistema son 4)

```
sudo su - oracle -c '$ORACLE_HOME/bin/dbca -silent -createDatabase \
  -templateName General_Purpose.dbc \
  -gdbname ORCL -sid ORCL \
  -createAsContainerDatabase true \
  -numberOfPDBs 1 -pdbName PDB1 \
  -sysPassword <PASSWORD> \
  -systemPassword <PASSWORD> \
  -pdbAdminPassword <PASSWORD> \
  -storageType FS \
  -datafileDestination /u01/oradata \
  -recoveryAreaDestination /u01/fast_recovery_area \
  -recoveryAreaSize 10240 \
  -characterSet AL32UTF8 \
  -nationalCharacterSet AL16UTF16 \
  -memoryMgmtType AUTO_SGA \
  -totalMemory 3072 \
  -emConfiguration NONE \
  -ignorePrereqFailure'

```

```
debian@oracle:~$ sudo su - oracle -c '$ORACLE_HOME/bin/dbca -silent -createDatabase ...'
[WARNING] [DBT-06801] Specified Fast Recovery Area size (10,240 MB) is less than the recommended value.
   CAUSE: Fast Recovery Area size should at least be three times the database size (4,141 MB).
   ACTION: Specify Fast Recovery Area Size to be at least three times the database size.
Prepare for db operation
8% complete
Copying database files
31% complete
Creating and starting Oracle instance
32% complete
36% complete
39% complete
42% complete
46% complete
Completing Database Creation
51% complete
53% complete
54% complete
Creating Pluggable Databases
58% complete
77% complete
Executing Post Configuration Actions
100% complete
Database creation complete. For details check the logfiles at:
 /u01/app/oracle/cfgtoollogs/dbca/ORCL.
Database Information:
Global Database Name:ORCL
System Identifier(SID):ORCL
Look at the log file "/u01/app/oracle/cfgtoollogs/dbca/ORCL/ORCL.log" for further details.


```

## 4. Configuración de Red TNS y Parámetros del SPFILE

### Configuración de tnsnames.ora

`dbca` genera por su cuenta un `tnsnames.ora` con entradas propias, entre ellas `LISTENER_ORCL`, el alias que la instancia usa por defecto para registrarse en el Listener. Por este motivo **no se debe sobrescribir el fichero**: se hace una copia de seguridad y se **añaden** los alias de conexión al final con `>>`.

```
sudo su - oracle -c 'cp $ORACLE_HOME/network/admin/tnsnames.ora $ORACLE_HOME/network/admin/tnsnames.ora.bak'
sudo su - oracle -c 'cat $ORACLE_HOME/network/admin/tnsnames.ora'

```

Revisamos el contenido y, si los alias `ORCL` y `PDB1` no aparecen ya, los añadimos para facilitar la resolución de nombres de la CDB (`ORCL`) y de la PDB (`PDB1`):

```
sudo su - oracle -c 'cat >> $ORACLE_HOME/network/admin/tnsnames.ora <<EOF

ORCL =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = ora26ai.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = ORCL)
    )
  )

PDB1 =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = ora26ai.example.com)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = PDB1)
    )
  )
EOF'

```

Validamos la resolución de los alias TNS:

```
sudo su - oracle -c 'tnsping ORCL'
sudo su - oracle -c 'tnsping PDB1'

```

```
debian@oracle:~$ sudo su - oracle -c 'tnsping ORCL'
TNS Ping Utility for Linux: Version 23.26.1.0.0 - Production on 06-OCT-2026 07:58:10

Copyright (c) 1997, 2026, Oracle.  All rights reserved.

Used parameter files:
/u01/app/oracle/product/26.0.0/dbhome_1/network/admin/sqlnet.ora


Used TNSNAMES adapter to resolve the alias
Attempting to contact (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = ora26ai.example.com)(PORT = 1521)) (CONNECT_DATA = (SERVER = DEDICATED) (SERVICE_NAME = ORCL)))
OK (0 msec)
debian@oracle:~$ sudo su - oracle -c 'tnsping PDB1'
TNS Ping Utility for Linux: Version 23.26.1.0.0 - Production on 06-OCT-2026 07:58:10

Copyright (c) 1997, 2026, Oracle.  All rights reserved.

Used parameter files:
/u01/app/oracle/product/26.0.0/dbhome_1/network/admin/sqlnet.ora


Used TNSNAMES adapter to resolve the alias
Attempting to contact (DESCRIPTION = (ADDRESS = (PROTOCOL = TCP)(HOST = ora26ai.example.com)(PORT = 1521)) (CONNECT_DATA = (SERVER = DEDICATED) (SERVICE_NAME = PDB1)))
OK (0 msec)


```

### Configuración de parámetros de arranque en el SPFILE

El **SPFILE** es el fichero binario de parámetros que Oracle lee al arrancar la instancia. Los cambios realizados con `SCOPE=BOTH` se aplican en caliente y se guardan en él, de modo que persisten en los siguientes arranques.

Durante la creación de la base de datos, `dbca` ya escribe en el SPFILE los parámetros principales: `db_name` y `db_unique_name` (a partir de `-gdbname`), `enable_pluggable_database` , `sga_target` y `pga_aggregate_target` (a partir de `-totalMemory`) o las rutas del área de recuperación. El nombre de la instancia se deduce de `ORACLE_SID`, y el nombre del servicio (`service_names`) toma por defecto el valor de `db_unique_name`. Por ello, en este paso solo comprobaremos que estos parámetros se asignasen correctamente.


```
sudo su - oracle -c 'sqlplus / as sysdba' <<'EOF'

-- Comprobar que la instancia ha arrancado utilizando un SPFILE
SHOW PARAMETER spfile;

-- Nombre de la base de datos, de la instancia y del servicio
SHOW PARAMETER db_name;
SHOW PARAMETER db_unique_name;
SHOW PARAMETER instance_name;
SHOW PARAMETER service_names;
EXIT;
EOF

```

```
debian@oracle:~$ sudo su - oracle -c 'sqlplus / as sysdba'

SQL*Plus: Release 23.26.1.0.0 - Production on Tue Oct 6 07:58:18 2026
Version 23.26.1.0.0

Copyright (c) 1982, 2025, Oracle.  All rights reserved.


Connected to:
Oracle AI Database 26ai Enterprise Edition Release 23.26.1.0.0 - Production
Version 23.26.1.0.0

SQL> SHOW PARAMETER spfile;
NAME								     TYPE	 VALUE
------------------------------------ ----------- ------------------------------
spfile								     string	 /u01/app/oracle/product/26.0.0
							/dbhome_1/dbs/spfileORCL.ora
SQL> SHOW PARAMETER db_name;
NAME								     TYPE	 VALUE
------------------------------------ ----------- ------------------------------
db_name 							     string	 ORCL
SQL> SHOW PARAMETER db_unique_name;
NAME								     TYPE	 VALUE
------------------------------------ ----------- ------------------------------
db_unique_name						     string	 ORCL
SQL> SHOW PARAMETER service_names;
NAME								     TYPE	 VALUE
------------------------------------ ----------- ------------------------------
service_names						     string	 ORCL


```

Si queremos, también podemos hacer otros cambios a la configuración del sistema, como por ejemplo asignar la dirección de listener directamente mediante el spfile, ya que por defecto este se asigna con una dirección en `tnsnames.ora`, asi que si queremos lo podemos poner nosotros implícitamente:
    
```
ALTER SYSTEM SET local_listener='(ADDRESS=(PROTOCOL=TCP)(HOST=ora26ai.example.com)(PORT=1521))' SCOPE=BOTH;
ALTER SYSTEM REGISTER;

```

Si quisiésemos podemos volcar el contenido del `SPFILE` en una copia en texto plano que si podemos leer directamente:
    
```
CREATE PFILE='/u01/app/oracle/init_ORCL_backup.ora' FROM SPFILE;

```

```
oracle@ora26ai:~$ cat /u01/app/oracle/init_ORCL_backup.ora
ORCL.__data_transfer_cache_size=0
ORCL.__datamemory_area_size=0
ORCL.__db_cache_size=1728053248
ORCL.__inmemory_ext_roarea=0
ORCL.__inmemory_ext_rwarea=0
ORCL.__java_pool_size=0
ORCL.__large_pool_size=16777216
ORCL.__oracle_base='/u01/app/oracle'#ORACLE_BASE set from environment
ORCL.__pga_aggregate_target=805306368
ORCL.__sga_target=2415919104
ORCL.__shared_io_pool_size=117440512
ORCL.__shared_pool_size=520093696
ORCL.__streams_pool_size=0
ORCL.__unified_pga_pool_size=0
ORCL._instance_recovery_bloom_filter_size=1048576
*.compatible='23.6.0'
*.control_files='/u01/oradata/ORCL/control01.ctl','/u01/fast_recovery_area/ORCL/control02.ctl'
*.db_block_size=8192
*.db_name='ORCL'
*.db_recovery_file_dest='/u01/fast_recovery_area'
*.db_recovery_file_dest_size=10240m
*.diagnostic_dest='/u01/app/oracle'
*.dispatchers='(PROTOCOL=TCP) (SERVICE=ORCLXDB)'
*.enable_pluggable_database=true
*.local_listener='(ADDRESS=(PROTOCOL=TCP)(HOST=ora26ai.example.com)(PORT=1521))'
*.nls_language='AMERICAN'
*.nls_territory='AMERICA'
*.open_cursors=300
*.pga_aggregate_target=768m
*.processes=300
*.remote_login_passwordfile='EXCLUSIVE'
*.sga_target=2304m
*.undo_tablespace='UNDOTBS1'

```

Ahora comprobamos que el Listener tiene registrados los servicios `ORCL`, `PDB1` y `ORCLXDB`, todos con la instancia `ORCL` en estado `READY`:

```
sudo su - oracle -c 'lsnrctl services'

```

```
debian@ora26ai:~$ sudo su - oracle -c 'lsnrctl services'

LSNRCTL for Linux: Version 23.26.1.0.0 - Production on 06-OCT-2026 14:03:14

Copyright (c) 1991, 2026, Oracle.  All rights reserved.

Connecting to (DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=ora26ai.example.com)(PORT=1521)))
Services Summary...
Service "5d28596bf4642fd0e063177aa8c022a5" has 1 instance(s).
  Instance "ORCL", status READY, has 1 handler(s) for this service...
    Handler(s):
      "DEDICATED" established:2 refused:0 state:ready
         LOCAL SERVER
Service "ORCL" has 1 instance(s).
  Instance "ORCL", status READY, has 1 handler(s) for this service...
    Handler(s):
      "DEDICATED" established:2 refused:0 state:ready
         LOCAL SERVER
Service "ORCLXDB" has 1 instance(s).
  Instance "ORCL", status READY, has 1 handler(s) for this service...
    Handler(s):
      "D000" established:0 refused:0 current:0 max:1022 state:ready
         DISPATCHER <machine: ora26ai.example.com, pid: 2032>
         (ADDRESS=(PROTOCOL=tcp)(HOST=ora26ai.example.com)(PORT=36161))
Service "pdb1" has 1 instance(s).
  Instance "ORCL", status READY, has 1 handler(s) for this service...
    Handler(s):
      "DEDICATED" established:2 refused:0 state:ready
         LOCAL SERVER
The command completed successfully

```

## 5. Automatización del Arranque del Servicio (`systemd`)


Para asegurar el arranque y parada automática de la base de datos y del Listener con el sistema operativo:

1. Editamos el archivo `/etc/oratab` sustituyendo el indicador `N` por `Y` en la entrada correspondiente a la instancia `ORCL`.

```
sudo sed -i 's|^ORCL:\(.*\):N$|ORCL:\1:Y|' /etc/oratab
grep ^ORCL /etc/oratab

```

```
debian@oracle:~$ grep ^ORCL /etc/oratab
ORCL:/u01/app/oracle/product/26.0.0/dbhome_1:Y


```

2. Creamos la unidad de servicio `systemd` en `/etc/systemd/system/oracle-db.service`:

```
sudo tee /etc/systemd/system/oracle-db.service <<'EOF'
[Unit]
Description=Oracle Database 26ai Service
After=network.target

[Service]
Type=forking
RemainAfterExit=yes
User=oracle
Group=oinstall
Environment="ORACLE_BASE=/u01/app/oracle"
Environment="ORACLE_HOME=/u01/app/oracle/product/26.0.0/dbhome_1"
Environment="ORACLE_SID=ORCL"
ExecStart=/u01/app/oracle/product/26.0.0/dbhome_1/bin/dbstart /u01/app/oracle/product/26.0.0/dbhome_1
ExecStop=/u01/app/oracle/product/26.0.0/dbhome_1/bin/dbshut /u01/app/oracle/product/26.0.0/dbhome_1
TimeoutStartSec=600
TimeoutStopSec=600
LimitNOFILE=65536
LimitNPROC=16384
LimitMEMLOCK=infinity

[Install]
WantedBy=multi-user.target
EOF

```

3. Recargamos la configuración de `systemd`, habilitamos e iniciamos el servicio:

```
sudo systemctl daemon-reload
sudo systemctl enable oracle-db.service
sudo systemctl start oracle-db.service
sudo systemctl status oracle-db.service

```

```
debian@oracle:~$ sudo systemctl status oracle-db.service
● oracle-db.service - Oracle Database 26ai Service
     Loaded: loaded (/etc/systemd/system/oracle-db.service; enabled; preset: enabled)
     Active: active (running) since Tue 2026-10-06 07:59:51 UTC; 27ms ago
 Invocation: 2b2195c780e54326abed9c6f23b41d3d
    Process: 12695 ExecStart=/u01/app/oracle/product/26.0.0/dbhome_1/bin/dbstart /u01/app/oracle/product/26.0.0/>
      Tasks: 100 (limit: 9486)
     Memory: 2.9G (peak: 3G)
        CPU: 14.065s
     CGroup: /system.slice/oracle-db.service
             ├─12807 ora_pmon_ORCL
             ├─12811 ora_clmn_ORCL
             ├─12815 ora_psp0_ORCL
             ├─12819 ora_vktm_ORCL
             ├─12825 ora_gen0_ORCL
             ├─12831 ora_mman_ORCL
             ├─12837 ora_gen2_ORCL
             ├─12839 ora_diag_ORCL
             ├─12843 ora_ofsd_ORCL
             ├─12845 ora_gwpd_ORCL
             ├─12847 ora_dbrm_ORCL
             ├─12849 ora_vkrm_ORCL
             ├─12851 ora_svcb_ORCL
             ├─12853 ora_pman_ORCL
             ├─12855 ora_dia0_ORCL
             ├─12858 ora_lmhb_ORCL
             ├─12862 ora_dbw0_ORCL
             ├─12865 ora_lgwr_ORCL
             ├─12867 ora_ckpt_ORCL
             ├─12869 ora_smon_ORCL
             ├─12871 ora_smco_ORCL
             ├─12873 ora_reco_ORCL
             ├─12876 ora_lreg_ORCL
             ├─12882 ora_pxmn_ORCL
             ├─12888 ora_mmon_ORCL
             ├─12891 ora_mmnl_ORCL


```

## 6. Verificación Final de Conectividad Local

Por último, comprobamos la conectividad usando los alias definidos en `tnsnames.ora` hacia la CDB y la PDB:

```
sudo su - oracle -c 'sqlplus system/<PASSWORD>@ORCL' <<'EOF'
SELECT name, open_mode, cdb FROM v$database;
EXIT;
EOF

sudo su - oracle -c 'sqlplus system/<PASSWORD>@PDB1' <<'EOF'
SELECT name, open_mode FROM v$pdbs;
EXIT;
EOF

```

```
debian@ora26ai:~$ sudo su - oracle -c 'sqlplus system/************@ORCL' <<'EOF'
SELECT name, open_mode, cdb FROM v$database;
EXIT;
EOF

SQL*Plus: Release 23.26.1.0.0 - Production on Tue Oct 6 14:04:40 2026
Version 23.26.1.0.0

Copyright (c) 1982, 2025, Oracle.  All rights reserved.

Last Successful login time: Tue Oct 06 2026 10:44:22 +00:00

Connected to:
Oracle AI Database 26ai Enterprise Edition Release 23.26.1.0.0 - Production
Version 23.26.1.0.0

SQL>
NAME      OPEN_MODE            CDB
--------- -------------------- ---
ORCL      READ WRITE           YES


debian@ora26ai:~$ sudo su - oracle -c 'sqlplus system/oracle@PDB1' <<'EOF'
SELECT name, open_mode FROM v$pdbs;
EXIT;
EOF

SQL*Plus: Release 23.26.1.0.0 - Production on Tue Oct 6 14:06:18 2026
Version 23.26.1.0.0

Copyright (c) 1982, 2025, Oracle.  All rights reserved.

Last Successful login time: Tue Oct 06 2026 14:04:40 +00:00

Connected to:
Oracle AI Database 26ai Enterprise Edition Release 23.26.1.0.0 - Production
Version 23.26.1.0.0

SQL>
NAME    OPEN_MODE
------- ----------
PDB1    READ WRITE

```