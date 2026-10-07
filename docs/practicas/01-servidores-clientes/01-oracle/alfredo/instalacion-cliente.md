# Guía de Instalación y Configuración de Oracle Instant Client en Linux

Esta guía describe el procedimiento para la instalación y configuración de Oracle Instant Client en entornos Debian13. También abarcaremos la resolución de nombres a través del archivo `tnsnames.ora`.

--- 

### Instalación de Dependencias del Sistema

La principal librería que se requiere es la librería `libaio` que la lectura y escritura de I/O asíncrona requerida por los binarios de Oracle.

En Debian 13 el paquete de la biblioteca `libaio1` se empaqueta como `libaio1t64` (`libaio.so.1t64`), pero el instalador de Oracle busca explícitamente el nombre tradicional `libaio.so.1`. Es por esto que tras descargarla, tambien creamos el enlace simbólico y actualizamos la caché de bibliotecas.


```
sudo apt update && sudo apt install -y libaio1t64 && \
sudo ln -s /usr/lib/x86_64-linux-gnu/libaio.so.1t64 /usr/lib/x86_64-linux-gnu/libaio.so.1 && \
sudo ldconfig

```

---

## Despliegue de Paquetes e Instalación del Cliente

Para garantizar un entorno estructurado y estandarizado, los binarios de Oracle Instant Client se ubican convencionalmente en la ruta `/opt/oracle`.

### Estructura de Directorios y Extracción de Binarios

Creación del directorio base y descompresión del paquete de software. Para ello debemos de obtener primero los paquetes Oracle Instant Client y SQLPLUS, los cuales podemos conseguir en [la web de Oracle](https://www.oracle.com/es/database/technologies/instant-client/linux-x86-64-downloads.html):

```
sudo mkdir -p /opt/oracle
sudo unzip instantclient-basic-linux.x64-*.zip -d /opt/oracle/
sudo unzip instantclient-sqlplus-linux.x64-*.zip -d /opt/oracle/

```

Verificación del contenido instalado en la ruta de destino:

```
ls -la /opt/oracle/instantclient_*

```

```
debian@cliente:~$ ls -a /opt/oracle/instantclient_*
 .                   libclntsh.so.11.1       libclntshcore.so.20.1   libocci.so.21.1   pkcs11.so
 ..                  libclntsh.so.12.1       libclntshcore.so.21.1   libocci.so.22.1   sqlplus
 adrci               libclntsh.so.18.1       libclntshcore.so.22.1   libocci.so.23.1   SQLPLUS_LICENSE
 BASIC_LICENSE       libclntsh.so.19.1       libclntshcore.so.23.1   libociei.so       SQLPLUS_README
 BASIC_README        libclntsh.so.20.1       libnnz.so               libocijdbc23.so   ucp.jar
 fips.so             libclntsh.so.21.1       libocci.so              libsqlplus.so     ucp11.jar
 fips1403.so         libclntsh.so.22.1       libocci.so.10.1         libsqlplusic.so   ucp17.jar
 genezi              libclntsh.so.23.1       libocci.so.11.1         libtfojdbc1.so    uidrvci
 glogin.sql          libclntshcore.so        libocci.so.12.1         network           xstreams.jar
 legacy.so           libclntshcore.so.12.1   libocci.so.18.1         ojdbc11.jar
 libclntsh.so        libclntshcore.so.18.1   libocci.so.19.1         ojdbc17.jar
 libclntsh.so.10.1   libclntshcore.so.19.1   libocci.so.20.1         ojdbc8.jar

```

---

## Configuración de Variables de Entorno y Enlaces del Sistema

Para garantizar que los binarios y librerías compartidas sean accesibles por los distintos usuarios del sistema, es necesario establecer las variables de entorno `LD_LIBRARY_PATH`, `PATH` y `TNS_ADMIN`.

### Configuración del Cargador de Librerías (`ldconfig`)

Para que el sistema reconozca las librerías dinámicas de Oracle sin depender exclusivamente de variables de entorno locales, se registra el directorio en la configuración global de `ldconfig`:

```
echo "/opt/oracle/instantclient_23_26" | sudo tee /etc/ld.so.conf.d/oracle-instantclient.conf
sudo ldconfig

```

Verificación del registro de librerías en la caché del sistema:

```
sudo ldconfig -p | grep clntsh

```

```
debian@cliente:~$ sudo ldconfig -p | grep clntsh
        libclntshcore.so.23.1 (libc6,x86-64) => /opt/oracle/instantclient_23_26/libclntshcore.so.23.1
        libclntshcore.so (libc6,x86-64) => /opt/oracle/instantclient_23_26/libclntshcore.so
        libclntsh.so.23.1 (libc6,x86-64) => /opt/oracle/instantclient_23_26/libclntsh.so.23.1
        libclntsh.so (libc6,x86-64) => /opt/oracle/instantclient_23_26/libclntsh.so

```

### Configuración de Variables Globales del Sistema

Se define un perfil global en `/etc/profile.d/oracle.sh` para la persistencia de las variables del cliente entre sesiones de usuario:

```
sudo tee /etc/profile.d/oracle.sh << 'EOF'
export ORACLE_BASE=/opt/oracle
export INSTANT_CLIENT_DIR=$ORACLE_BASE/instantclient_23_26
export PATH=$PATH:$INSTANT_CLIENT_DIR
export LD_LIBRARY_PATH=$INSTANT_CLIENT_DIR:$LD_LIBRARY_PATH
export TNS_ADMIN=$INSTANT_CLIENT_DIR/network/admin
EOF

sudo chmod 644 /etc/profile.d/oracle.sh
source /etc/profile.d/oracle.sh

```

---

## Configuración de Red y Resolución de Nombres (`tnsnames.ora`)

El archivo `tnsnames.ora` actúa como la tabla de resolución de nombres de servicio para las conexiones Oracle Client.

### Creación del Directorio de Red y Archivo de Configuración

```
sudo mkdir -p $TNS_ADMIN

```

Creación del archivo `$TNS_ADMIN/tnsnames.ora` definiendo el alias de conexión correspondiente, en este caso declarare las conexiones para el area PBD1 en el servidor:

```
sudo tee -a $TNS_ADMIN/tnsnames.ora << 'EOF'
PDB1 =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = TU_DOMINIO/IP)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = PDB1)
    )
  )
EOF

```

Verificación del contenido y permisos del archivo de red configurado:

```
cat $TNS_ADMIN/tnsnames.ora

```

```
debian@cliente:~$ cat $TNS_ADMIN/tnsnames.ora
PBD1 =
  (DESCRIPTION =
    (ADDRESS = (PROTOCOL = TCP)(HOST = 192.168.122.23)(PORT = 1521))
    (CONNECT_DATA =
      (SERVER = DEDICATED)
      (SERVICE_NAME = PBD1)
    )
  )

```

---

## Verificación de Conectividad y Pruebas del Servicio

Una vez aplicadas las variables y archivos de red, se procede a validar el correcto funcionamiento de los binarios y la comunicación con el servidor de base de datos remoto.

### Comprobación de Binarios y Enlaces Dinámicos

Verificación de la resolución de dependencias del ejecutable `sqlplus`:

```
ldd $(which sqlplus)

```

```
debian@cliente:~$ ldd $(which sqlplus)
        linux-vdso.so.1 (0x00007f9fafc6a000)
        libsqlplus.so => /opt/oracle/instantclient_23_26/libsqlplus.so (0x00007f9fafb50000)
        libclntsh.so.23.1 => /opt/oracle/instantclient_23_26/libclntsh.so.23.1 (0x00007f9fa9e00000)
        libclntshcore.so.23.1 => /opt/oracle/instantclient_23_26/libclntshcore.so.23.1 (0x00007f9fa9800000)
        libnnz.so => /opt/oracle/instantclient_23_26/libnnz.so (0x00007f9fa8c00000)
        libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007f9fafb29000)
        libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007f9fafa39000)
        libpthread.so.0 => /lib/x86_64-linux-gnu/libpthread.so.0 (0x00007f9fafa34000)
        librt.so.1 => /lib/x86_64-linux-gnu/librt.so.1 (0x00007f9fafa2f000)
        libaio.so.1 => /lib/x86_64-linux-gnu/libaio.so.1 (0x00007f9fafa2a000)
        libresolv.so.2 => /lib/x86_64-linux-gnu/libresolv.so.2 (0x00007f9fafa18000)
        libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f9fa8a0c000)
        /lib64/ld-linux-x86-64.so.2 (0x00007f9fafc6c000)

```

### Prueba de Conectividad con la Base de Datos

Ahora podemos probar la conexion con la base de datos usando el alias que hemos definido en `tnsnames.ora`:

```
sqlplus SCOTT@PBD1

```

```
debian@prueba:~$ sqlplus SCOTT@PDB1

SQL*Plus: Release 23.26.3.0.0 - Production on Tue Oct 6 18:30:12 2026
Version 23.26.3.0.0

Copyright (c) 1982, 2026, Oracle.  All rights reserved.

Enter password:
Last Successful login time: Tue Oct 06 2026 18:29:37 +02:00

Connected to:
Oracle AI Database 26ai Enterprise Edition Release 23.26.1.0.0 - Production
Version 23.26.1.0.0

SQL>

```